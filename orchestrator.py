import asyncio
import uuid
from typing import Any, AsyncIterator, List, Optional, Tuple

from agent_factory import build_agent_for_servers
from agent_router import route_question
from config import settings
from rewrite import rewrite_query


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
) -> List[Any]:
    """Run one phase (SQL or RAG) and return updated messages."""
    if not servers:
        return messages
    agent = await build_agent_for_servers(servers, tools_timeout_s)
    out = await asyncio.wait_for(
        agent.ainvoke({"messages": messages}),
        timeout=invoke_timeout_s,
    )
    return out["messages"]


async def _run_both_phases(
    messages: list,
    sql_servers: dict,
    rag_servers: dict,
    tools_timeout_s: float,
    invoke_timeout_s: float,
) -> List[Any]:
    """Run SQL phase then RAG phase; return updated messages."""
    for servers in (sql_servers, rag_servers):
        messages = await _run_phase(messages, servers, tools_timeout_s, invoke_timeout_s)
    return messages


def _select_phase(
    sql_servers: dict,
    rag_servers: dict,
    route: str,
) -> Tuple[dict, dict]:
    """Return (sql_servers, rag_servers) to run based on route. Route is 'RAG' or 'SQL'."""
    if route == "SQL":
        return sql_servers, {}
    if route == "RAG":
        return {}, rag_servers
    return sql_servers, rag_servers


async def run_agent(
    query: str,
    *,
    tools_timeout_s: float = 10.0,
    invoke_timeout_s: float = 30.0,
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict:
    sql_servers, rag_servers = settings.sql_server_config, settings.rag_server_config
    query = await rewrite_query(query, request_id=request_id, session_id=session_id)
    messages = [{"role": "user", "content": query}]
    route = await route_question(query, request_id=request_id, session_id=session_id)
    sql_servers, rag_servers = _select_phase(sql_servers, rag_servers, route)
    messages = await _run_both_phases(
        messages, sql_servers, rag_servers, tools_timeout_s, invoke_timeout_s
    )
    return {"messages": messages}


async def answer_query_sync(query: str, **kwargs: Any) -> str:
    """Run agent (route to SQL or RAG when both configured) and return the final answer."""
    out = await run_agent(query, **kwargs)
    return _last_ai_content(out["messages"])


async def stream_answer_query(
    query: str,
    *,
    session_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> AsyncIterator[dict]:
    """Stream the assistant reply. Routes to SQL or RAG when both configured.
    Yields request_id first; then state/rewrite/route/answer events."""
    request_id = request_id or str(uuid.uuid4())
    try:
        sql_servers, rag_servers = settings.sql_server_config, settings.rag_server_config
        yield {"type": "request_id", "session_id": session_id, "request_id": request_id}
        yield {"type": "state", "phase": "rewrite", "message": "Rewriting question..."}
        query = await rewrite_query(query, request_id=request_id, session_id=session_id)
        yield {"type": "rewrite", "text": query}
        yield {"type": "state", "phase": "route", "message": "Routing question..."}
        route = await route_question(query, request_id=request_id, session_id=session_id)
        sql_servers, rag_servers = _select_phase(sql_servers, rag_servers, route)
        yield {"type": "route", "route": route}
        messages = [{"role": "user", "content": query}]
        for phase, servers in [("sql", sql_servers), ("rag", rag_servers)]:
            if servers:
                yield {"type": "state", "phase": phase, "message": f"Running {phase.upper()} phase..."}
                messages = await _run_phase(
                    messages, servers,
                    settings.tools_timeout_s,
                    settings.invoke_timeout_s,
                )
        content = _last_ai_content(messages)
        if content:
            yield {"type": "answer", "text": content}
        yield {"type": "state", "phase": "done", "message": "Complete"}
    except Exception as e:
        yield {"type": "error", "text": format_error(e)}


def format_error(e: Exception) -> str:
    """Unwrap ExceptionGroup so the real cause is shown."""
    sub = getattr(e, "exceptions", None)
    if sub:
        return f"Error: {type(sub[0]).__name__}: {sub[0]}"
    return f"Error: {type(e).__name__}: {e}"
