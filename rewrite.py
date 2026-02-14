"""Query rewriting for better SQL/RAG retrieval."""
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config import get_langsmith_tags, settings

_SYSTEM = """Rewrite the user's question to be clearer and more specific for retrieval.
Keep it concise. Return only the rewritten question, nothing else."""


async def rewrite_query(query: str) -> str:
    """Refine the user query for better SQL/RAG retrieval."""
    if not query or not query.strip():
        return query
    llm = ChatOpenAI(model=settings.openai_model, temperature=0)
    msg = await llm.ainvoke(
        [SystemMessage(content=_SYSTEM), HumanMessage(content=query)],
        config={"tags": get_langsmith_tags()},
    )
    rewritten = (msg.content or "").strip()
    return rewritten if rewritten else query
