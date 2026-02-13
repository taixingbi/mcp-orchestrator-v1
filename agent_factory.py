"""Build LangGraph agents from MCP server configs (with caching)."""
import asyncio
from typing import Any, Dict, Literal, Tuple

from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode

from config import settings

_agent_cache: Dict[Tuple[str, float], Any] = {}


def _should_continue(state: MessagesState) -> Literal["tool_node", "__end__"]:
    last = state["messages"][-1]
    return "tool_node" if getattr(last, "tool_calls", None) else "__end__"


async def build_agent_for_servers(servers: dict, tools_timeout_s: float = 60.0):
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
    llm = ChatOpenAI(model=settings.openai_model, temperature=0).bind_tools(tools)

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
