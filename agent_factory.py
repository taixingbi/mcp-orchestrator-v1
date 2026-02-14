"""Build LangGraph agents from MCP server configs (with caching)."""
import asyncio
from typing import Any, Dict, Literal, Tuple

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import MessagesState
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from answer_judge import MAX_RETRIES, evaluate_answer
from config import settings

_agent_cache: Dict[Tuple[str, float], Any] = {}


class AgentState(MessagesState, total=False):
    retry_count: int
    judge_passed: bool


def _extract_content(msg: Any) -> str:
    c = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else None)
    return str(c) if c else ""


def _should_continue(state: AgentState) -> Literal["tool_node", "judge"]:
    last = state["messages"][-1]
    tool_calls = getattr(last, "tool_calls", None) or (last.get("tool_calls") if isinstance(last, dict) else None)
    return "tool_node" if tool_calls else "judge"


def _judge_continue(state: AgentState) -> Literal["__end__", "llm_call"]:
    return "__end__" if state.get("judge_passed") else "llm_call"


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

    async def llm_call(state: AgentState):
        result = await llm.ainvoke(state["messages"])
        return {"messages": [result]}

    async def judge_node(state: AgentState):
        messages = state["messages"]
        retry_count = state.get("retry_count", 0)
        if retry_count >= MAX_RETRIES:
            return {"judge_passed": True}
        question = ""
        answer = ""
        for m in messages:
            role = getattr(m, "type", None) or (m.get("role") if isinstance(m, dict) else None)
            if role in ("human", "user") and not question:
                question = _extract_content(m)
            elif role == "ai":
                answer = _extract_content(m)
        passed, feedback = await evaluate_answer(question, answer)
        if passed or retry_count >= MAX_RETRIES:
            return {"judge_passed": True}
        return {
            "judge_passed": False,
            "messages": [HumanMessage(content=f"The previous answer was not good enough. Reason: {feedback} Please improve your answer.")],
            "retry_count": retry_count + 1,
        }

    g = StateGraph(AgentState)
    g.add_node("llm_call", llm_call)
    g.add_node("tool_node", tool_node)
    g.add_node("judge", judge_node)
    g.add_edge(START, "llm_call")
    g.add_conditional_edges("llm_call", _should_continue, ["tool_node", "judge"])
    g.add_edge("tool_node", "llm_call")
    g.add_conditional_edges("judge", _judge_continue, ["__end__", "llm_call"])
    compiled = g.compile()
    _agent_cache[cache_key] = compiled
    return compiled
