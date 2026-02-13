import asyncio
from typing import Any, AsyncIterator, List

from dotenv import load_dotenv

from agent_factory import build_agent_for_servers
from config import settings
from mcp_tools import get_server_configs
from rewrite import rewrite_query

load_dotenv()

_STREAM_CONFIG = {"configurable": {}}


def _extract_ai_content(msg: Any) -> str:
    content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def _ensure_servers() -> tuple:
    """Return (sql_servers, rag_servers); raise if both empty."""
    sql_servers, rag_servers = get_server_configs()
    if not sql_servers and not rag_servers:
        raise ValueError("At least one of MCP_TOOL_SQL_URL or MCP_TOOL_RAG_URL must be set")
    return sql_servers, rag_servers


def _last_ai_content(messages: List[Any]) -> str:
    """Return the text content of the last AI message in the list."""
    for msg in reversed(messages):
        is_ai = getattr(msg, "type", None) == "ai" or (isinstance(msg, dict) and msg.get("type") == "ai")
        if is_ai:
            return _extract_ai_content(msg) or ""
    return ""


async def _run_phase(
    messages: list,
    servers: dict,
    tools_timeout_s: float,
    invoke_timeout_s: float,
) -> list:
    """Run one phase (SQL or RAG) and return updated messages."""
    if not servers:
        return messages
    agent = await build_agent_for_servers(servers, tools_timeout_s)
    out = await asyncio.wait_for(
        agent.ainvoke({"messages": messages}),
        timeout=invoke_timeout_s,
    )
    return out["messages"]


async def run_agent(
    query: str,
    *,
    tools_timeout_s: float = 10.0,
    invoke_timeout_s: float = 30.0,
) -> dict:
    sql_servers, rag_servers = _ensure_servers()
    if settings.rewrite_query:
        query = await rewrite_query(query)
    messages = [{"role": "user", "content": query}]
    messages = await _run_phase(messages, sql_servers, tools_timeout_s, invoke_timeout_s)
    messages = await _run_phase(messages, rag_servers, tools_timeout_s, invoke_timeout_s)
    return {"messages": messages}


async def answer_query_sync(query: str, **kwargs: Any) -> str:
    """Run agent (SQL then RAG) and return the final answer as a single string."""
    out = await run_agent(query, **kwargs)
    return _last_ai_content(out["messages"])


async def stream_answer_query(query: str) -> AsyncIterator[dict]:
    """Stream the final assistant reply. Runs SQL tools first, then RAG tools."""
    try:
        sql_servers, rag_servers = _ensure_servers()
        if settings.rewrite_query:
            query = await rewrite_query(query)
            yield {"type": "rewrite", "text": query}
        messages = [{"role": "user", "content": query}]
        messages = await _run_phase(
            messages, sql_servers, settings.tools_timeout_s, settings.invoke_timeout_s
        )

        if rag_servers:
            agent_rag = await build_agent_for_servers(
                rag_servers, tools_timeout_s=settings.tools_timeout_s
            )
            last_content = ""
            async for chunk in agent_rag.astream(
                {"messages": messages}, stream_mode="values", config=_STREAM_CONFIG
            ):
                if not chunk or "messages" not in chunk:
                    continue
                for msg in chunk["messages"]:
                    if getattr(msg, "type", None) != "ai":
                        continue
                    last_content = _extract_ai_content(msg) or last_content
            if last_content:
                yield {"type": "answer", "text": last_content}
        else:
            content = _last_ai_content(messages)
            if content:
                yield {"type": "answer", "text": content}
    except Exception as e:
        yield {"type": "error", "text": format_error(e)}


def format_error(e: Exception) -> str:
    """Unwrap ExceptionGroup so the real cause is shown."""
    sub = getattr(e, "exceptions", None)
    if sub:
        return f"Error: {type(sub[0]).__name__}: {sub[0]}"
    return f"Error: {type(e).__name__}: {e}"
