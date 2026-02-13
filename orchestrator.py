import asyncio
from typing import Any, AsyncIterator, Literal, Tuple, Dict, List

from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient

from mcp_tools import get_server_configs

load_dotenv()

_STREAM_CONFIG = {"configurable": {}}
_STREAM_TOOLS_TIMEOUT_S = 60.0
_STREAM_INVOKE_TIMEOUT_S = 120.0
_agent_cache: Dict[Tuple[str, float], Any] = {}


def _should_continue(state: MessagesState) -> Literal["tool_node", "__end__"]:
    last = state["messages"][-1]
    return "tool_node" if getattr(last, "tool_calls", None) else "__end__"


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


async def answer_query_sync(query: str, **kwargs: Any) -> str:
    """Run agent (SQL then RAG) and return the final answer as a single string."""
    out = await run_agent(query, **kwargs)
    return _last_ai_content(out["messages"])


async def stream_answer_query(query: str) -> AsyncIterator[str]:
    """Stream the final assistant reply. Runs SQL tools first, then RAG tools."""
    try:
        sql_servers, rag_servers = get_server_configs()
        if not sql_servers and not rag_servers:
            yield "Error: At least one of MCP_TOOL_SQL_URL or MCP_TOOL_RAG_URL must be set"
            return
        messages = [{"role": "user", "content": query}]
        messages = await _run_phase(
            messages, sql_servers, _STREAM_TOOLS_TIMEOUT_S, _STREAM_INVOKE_TIMEOUT_S
        )

        if rag_servers:
            agent_rag = await _build_agent_for_servers(
                rag_servers, tools_timeout_s=_STREAM_TOOLS_TIMEOUT_S
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
                yield last_content
        else:
            content = _last_ai_content(messages)
            if content:
                yield content
    except Exception as e:
        yield _format_error(e)


def _format_error(e: Exception) -> str:
    """Unwrap ExceptionGroup so the real cause is shown."""
    sub = getattr(e, "exceptions", None)
    if sub:
        return f"Error: {type(sub[0]).__name__}: {sub[0]}"
    return f"Error: {type(e).__name__}: {e}"
