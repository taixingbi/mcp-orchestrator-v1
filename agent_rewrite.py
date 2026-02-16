"""Query rewriting for better SQL/RAG retrieval."""
import re
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from config import get_langsmith_tags, get_llm

CANDIDATE_NAME = "Taixing Bi"


def rewrite_to_third_person(question: str) -> str:
    """Rewrite second-person references (you, your, etc.) to third person (candidate name)."""
    q = question
    replacements = [
        (r"\byourself\b", CANDIDATE_NAME),
        (r"\byou\b", CANDIDATE_NAME),
        (r"\byour\b", f"{CANDIDATE_NAME}'s"),
        (r"\bare you\b", f"is {CANDIDATE_NAME}"),
        (r"\bdo you\b", f"does {CANDIDATE_NAME}"),
        (r"\bhave you\b", f"has {CANDIDATE_NAME}"),
        (r"\bcan you\b", f"can {CANDIDATE_NAME}"),
    ]
    for pattern, repl in replacements:
        q = re.sub(pattern, repl, q, flags=re.IGNORECASE)
    return q


_SYSTEM = """Rewrite the user's question to be clearer and more specific for retrieval.
Keep it concise. Return only the rewritten question, nothing else."""


async def rewrite_query(
    query: str,
    *,
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> str:
    """Refine the user query for better SQL/RAG retrieval."""
    if not query or not query.strip():
        return query
    query = rewrite_to_third_person(query)
    llm = get_llm()
    msg = await llm.ainvoke(
        [SystemMessage(content=_SYSTEM), HumanMessage(content=query)],
        config={
            "run_name": "agent_rewrite",
            "tags": get_langsmith_tags(request_id=request_id, session_id=session_id),
        },
    )
    rewritten = (msg.content or "").strip()
    return rewritten if rewritten else query
