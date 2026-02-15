"""Judge agent: evaluate answer quality; if not good, provide feedback for retry."""
from typing import Optional, Tuple

from config import get_langsmith_tags, get_llm

MAX_RETRIES = 2

JUDGE_PROMPT = """You are a strict judge. Evaluate if the answer adequately addresses the question.

Criteria: relevance, correctness, completeness.

Return ONLY one line:
- GOOD  -> if the answer is satisfactory
- NOT_GOOD: <brief reason>  -> if the answer is weak, off-topic, or incomplete

Return ONLY: GOOD or NOT_GOOD: <reason>"""


async def evaluate_answer(
    question: str,
    answer: str,
    *,
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """Evaluate answer quality. Returns (passed, feedback). If passed, feedback is None."""
    if not answer or not answer.strip():
        return False, "Answer is empty."
    llm = get_llm()
    tags = get_langsmith_tags(request_id=request_id, session_id=session_id)
    resp = await llm.ainvoke(
        JUDGE_PROMPT + f"\nQuestion: {question}\n\nAnswer: {answer}",
        config={"run_name": "Answer Judge", "tags": tags},
    )
    text = (resp.content or "").strip().upper()
    if text.startswith("GOOD"):
        return True, None
    if text.startswith("NOT_GOOD"):
        reason = text.split(":", 1)[-1].strip() if ":" in text else "Answer needs improvement."
        return False, reason
    return True, None  # default pass on parse failure
