import asyncio
import uuid
from typing import Any, AsyncIterator, List, Optional, Tuple

from langchain_core.callbacks import AsyncCallbackHandler

from agent_graph import build_graph_agent
from agent_router import route_question
from agent_rewrite import rewrite_query
from config import get_langsmith_tags, settings
from utils import last_ai_content


class _AgentRunIdCallback(AsyncCallbackHandler):
    """Capture LangSmith run_id of the root agent_graph run."""

    def __init__(self, run_ids: List[str]):
        self.run_ids = run_ids

    async def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, **kwargs):
        if parent_run_id is None:
            self.run_ids.append(str(run_id))


async def run_graph(
    messages: list,
    servers: dict,
    tools_timeout_s: float,
    invoke_timeout_s: float,
    *,
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Tuple[List[Any], Optional[str]]:
    """Run one phase (SQL or RAG) and return (messages, agent_graph_run_id). agent_graph_run_id from LangSmith."""
    if not servers:
        return messages, None
    agent = await build_graph_agent(servers, tools_timeout_s)
    run_ids: List[str] = []
    callback = _AgentRunIdCallback(run_ids)
    out = await asyncio.wait_for(
        agent.ainvoke(
            {"messages": messages},
            config={
                "run_name": "agent_graph",
                "callbacks": [callback],
                "tags": get_langsmith_tags(request_id=request_id, session_id=session_id),
            },
        ),
        timeout=invoke_timeout_s,
    )
    agent_graph_run_id = run_ids[0] if run_ids else None
    return out["messages"], agent_graph_run_id


def _select_phase(
    sql_servers: dict,
    rag_servers: dict,
    route: str,
) -> Tuple[dict, dict]:
    """Return (sql_servers, rag_servers) to run based on route. Route is 'RAG', 'SQL', or 'BOTH'."""
    if route == "SQL":
        return sql_servers, {}
    if route == "RAG":
        return {}, rag_servers
    return sql_servers, rag_servers


async def answer_query_sync(
    query: str,
    *,
    tools_timeout_s: Optional[float] = None,
    invoke_timeout_s: Optional[float] = None,
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> str:
    """Run agent and return the final answer. Consumes stream_answer_query for single code path."""
    answer = ""
    async for event in stream_answer_query(
        query,
        request_id=request_id,
        session_id=session_id,
        tools_timeout_s=tools_timeout_s,
        invoke_timeout_s=invoke_timeout_s,
    ):
        if event.get("type") == "answer":
            answer = event.get("text", "")
        elif event.get("type") == "error":
            return event.get("text", "Unknown error")
    return answer


async def stream_answer_query(
    query: str,
    *,
    session_id: Optional[str] = None,
    request_id: Optional[str] = None,
    tools_timeout_s: Optional[float] = None,
    invoke_timeout_s: Optional[float] = None,
) -> AsyncIterator[dict]:
    """Stream the assistant reply. Routes to SQL or RAG when both configured.
    Yields request_id first; then state/rewrite/route/answer events."""
    request_id = request_id or str(uuid.uuid4())
    tools_s = tools_timeout_s if tools_timeout_s is not None else settings.tools_timeout_s
    invoke_s = invoke_timeout_s if invoke_timeout_s is not None else settings.invoke_timeout_s
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
        agent_graph_run_id = None
        for phase, servers in [("sql", sql_servers), ("rag", rag_servers)]:
            if servers:
                yield {"type": "state", "phase": phase, "message": f"Running {phase.upper()} phase..."}
                messages, agent_graph_run_id = await run_graph(
                    messages, servers, tools_s, invoke_s,
                    request_id=request_id, session_id=session_id,
                )
        content = last_ai_content(messages)
        if content:
            event = {"type": "answer", "text": content}
            if agent_graph_run_id:
                event["agent_graph_run_id"] = agent_graph_run_id
            yield event
        yield {"type": "state", "phase": "done", "message": "Complete"}
    except Exception as e:
        yield {"type": "error", "text": format_error(e)}


def format_error(e: Exception) -> str:
    """Unwrap ExceptionGroup so the real cause is shown."""
    sub = getattr(e, "exceptions", None)
    if sub:
        return f"Error: {type(sub[0]).__name__}: {sub[0]}"
    return f"Error: {type(e).__name__}: {e}"
