import asyncio
import os
from typing import Any, AsyncIterator, Literal, Tuple, Dict

from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient

from mcp_tools import get_server_configs

load_dotenv()

_STREAM_CONFIG = {"configurable": {}}
_agent_cache: Dict[Tuple[str, float], Any] = {}


def _should_continue(state: MessagesState) -> Literal["tool_node", "__end__"]:
    last = state["messages"][-1]
    return "tool_node" if getattr(last, "tool_calls", None) else "__end__"


def _extract_ai_content(msg: Any) -> str:
    content = getattr(msg, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


async def _build_agent_for_servers(servers: dict, tools_timeout_s: float = 60.0):
    """Build (or return cached) compiled LangGraph agent for the given MCP server config."""
    if not servers:
        raise ValueError("servers must be non-empty")
    url = next(iter(servers.values()))["url"].rstrip("/")
    cache_key = (url, tools_timeout_s)
    if cache_key in _agent_cache:
        return _agent_cache[cache_key]
    client = MultiServerMCPClient(servers, tool_name_prefix=False)
    tools = await asyncio.wait_for(client.get_tools(), timeout=tools_timeout_s)
    tool_node = ToolNode(tools)
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools(tools)

    def llm_call(state: MessagesState):
        return {"messages": [llm.invoke(state["messages"])]}

    g = StateGraph(MessagesState)
    g.add_node("llm_call", llm_call)
    g.add_node("tool_node", tool_node)
    g.add_edge(START, "llm_call")
    g.add_conditional_edges("llm_call", _should_continue, ["tool_node", END])
    g.add_edge("tool_node", "llm_call")
    compiled = g.compile()
    _agent_cache[cache_key] = compiled
    return compiled


async def _run_phase(
    messages: list,
    servers: dict,
    tools_timeout_s: float,
    invoke_timeout_s: float,
) -> list:
    """Run one phase (SQL or RAG) and return updated messages."""
    if not servers:
        return messages
    agent = await _build_agent_for_servers(servers, tools_timeout_s)
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
    sql_servers, rag_servers = get_server_configs()
    if not sql_servers and not rag_servers:
        raise ValueError("At least one of MCP_TOOL_SQL_URL or MCP_TOOL_RAG_URL must be set")
    messages = [{"role": "user", "content": query}]
    messages = await _run_phase(messages, sql_servers, tools_timeout_s, invoke_timeout_s)
    messages = await _run_phase(messages, rag_servers, tools_timeout_s, invoke_timeout_s)
    return {"messages": messages}


async def stream_answer_query(query: str) -> AsyncIterator[str]:
    """Stream the final assistant reply. Runs SQL tools first, then RAG tools."""
    try:
        sql_servers, rag_servers = get_server_configs()
        if not sql_servers and not rag_servers:
            yield "Error: At least one of MCP_TOOL_SQL_URL or MCP_TOOL_RAG_URL must be set"
            return
        messages = [{"role": "user", "content": query}]
        messages = await _run_phase(messages, sql_servers, 60.0, 120.0)

        if rag_servers:
            agent_rag = await _build_agent_for_servers(rag_servers, tools_timeout_s=60.0)
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
                yield last_content
        else:
            for msg in reversed(messages):
                if getattr(msg, "type", None) == "ai":
                    content = _extract_ai_content(msg)
                    if content:
                        yield content
                    break
    except Exception as e:
        yield _format_error(e)


def _format_error(e: Exception) -> str:
    """Unwrap ExceptionGroup so the real cause is shown."""
    sub = getattr(e, "exceptions", None)
    if sub and len(sub) > 0:
        first = sub[0]
        return f"Error: {type(first).__name__}: {first}"
    return f"Error: {type(e).__name__}: {e}"
