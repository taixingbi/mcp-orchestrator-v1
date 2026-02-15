"""Router agent: classify question as RAG or SQL for single-phase execution."""
from typing import Optional

from config import get_langsmith_tags, get_llm

ROUTER_PROMPT = """
You are a strict router. Return ONLY one of: RAG, SQL, or BOTH.

RAG (person/candidate): If question mentions Taixing, Bi → RAG.
  Topics: background, resume, skills, experience; visa sponsorship; LLM, LangChain, RAG;
  companies worked for; ML vs infrastructure; production AI fit; cloud/backend; seniority; deployments.

SQL (institutional/dataset): Keywords: jurisdiction, amount, salary, pay band, classification.
  Topics: government/public-sector job roles; salary ranges, compensation, pay bands, levels;
  job descriptions, responsibilities, requirements; role comparisons; labor-market data.
  No personal/candidate info.

Return ONLY: RAG, SQL, or BOTH.
"""


async def route_question(
    question: str,
    *,
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> str:
    """Classify question as 'RAG' or 'SQL'. Uses LLM with router prompt."""
    llm = get_llm()
    resp = await llm.ainvoke(
        ROUTER_PROMPT + f"\nQuestion: {question}",
        config={
        "run_name": "agent_router",
        "tags": get_langsmith_tags(request_id=request_id, session_id=session_id),
    },
    )
    return (resp.content or "").strip().upper()
