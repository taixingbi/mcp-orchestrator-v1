# main.py — MCP HTTP server exposing RAG tools
import contextlib
import json
import logging
from typing import Literal, Optional

from pydantic import BaseModel, Field
from langsmith import Client
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from mcp.server import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from config import settings
from orchestrator import answer_query_sync, format_error, stream_answer_query

# streamable_http_path="/" so mounted at /mcp matches (path becomes /)
mcp = FastMCP(
    settings.mcp_name,
    stateless_http=True,
    streamable_http_path="/",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False
    ),
)


@mcp.tool()
async def answer_question(question: str) -> str:
    """Answer a question using SQL then RAG tools. Returns the full answer text."""
    try:
        return await answer_query_sync(
            question,
            tools_timeout_s=settings.tools_timeout_s,
            invoke_timeout_s=settings.invoke_timeout_s,
        )
    except Exception as e:
        return format_error(e)


def _sse_stream_answer_gen(question: str):
    """Async generator for POST /stream-answer. Yields SSE events from stream_answer_query.
    Chunks: {type: 'run_id', run_id}, {type: 'state', phase, message}, {type: 'rewrite'|'answer', text}, {type: 'error', text}."""
    async def _gen():
        async for chunk in stream_answer_query(question):
            yield f"data: {json.dumps(chunk)}\n\n"
    return _gen()


mcp_app = mcp.streamable_http_app()


@contextlib.asynccontextmanager
async def _lifespan(_app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(
    title=settings.mcp_name,
    version=settings.app_version or "0.1.0",
    lifespan=_lifespan,
)


class StreamAnswerBody(BaseModel):
    question: str


FEEDBACK_TYPES = [
    "not_relevant",
    "biased",
    "not_factual",
    "incomplete_instructions",
    "unsafe",
    "style_tone",
    "other",
]


class FeedbackBody(BaseModel):
    """Feedback on an agent response."""

    run_id: Optional[str] = Field(None, description="LangSmith run_id from stream-answer (optional)")
    question: Optional[str] = Field(None, description="Original question (optional)")
    answer_snippet: Optional[str] = Field(None, description="Snippet of answer being rated (optional)")
    rating: Literal["thumbs_up", "thumbs_down"] = Field(..., description="Thumbs up or down")
    feedback_type: Optional[str] = Field(
        None,
        description="Predefined type: not_relevant, biased, not_factual, incomplete_instructions, unsafe, style_tone, other",
    )
    comment: Optional[str] = Field(None, description="Additional free-text feedback (optional)")


@app.post("/stream-answer")
async def stream_answer(body: StreamAnswerBody):
    """Stream the agent's answer as Server-Sent Events. Body: {"question": "..."}.
    Events: {type: "run_id", run_id}, {type: "state", phase, message}, {type: "rewrite"|"answer", text}, {type: "error", text}."""
    return StreamingResponse(
        _sse_stream_answer_gen(body.question),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _submit_langsmith_feedback(
    run_id: str,
    rating: Literal["thumbs_up", "thumbs_down"],
    feedback_type: Optional[str],
    comment: Optional[str],
) -> bool:
    """Submit feedback to LangSmith. Returns True if sent, False if skipped (no API key)."""
    if not settings.langchain_api_key and not getattr(settings, "langsmith_api_key", None):
        return False
    try:
        client = Client()
        score = 1.0 if rating == "thumbs_up" else -1.0
        client.create_feedback(
            run_id=run_id,
            key="user_rating",
            score=score,
            value=feedback_type or rating,
            comment=comment,
        )
        return True
    except Exception as e:
        logging.warning("langsmith create_feedback failed: %s", e)
        return False


@app.post("/feedback")
async def submit_feedback(body: FeedbackBody):
    """Submit feedback on an agent response (thumbs up/down, type, optional comment)."""
    if body.feedback_type and body.feedback_type not in FEEDBACK_TYPES:
        return {"status": "error", "message": f"feedback_type must be one of: {FEEDBACK_TYPES}"}
    logging.info(
        "feedback: rating=%s type=%s run_id=%s question=%s comment=%s",
        body.rating,
        body.feedback_type,
        body.run_id or None,
        (body.question or "")[:50] or None,
        (body.comment or "")[:50] or None,
    )
    if body.run_id and (settings.langchain_api_key or settings.langsmith_tracing):
        _submit_langsmith_feedback(
            run_id=body.run_id,
            rating=body.rating,
            feedback_type=body.feedback_type,
            comment=body.comment,
        )
    return {"status": "ok", "message": "Feedback received"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "app_version": settings.app_version,
        "mcp_name": settings.mcp_name,
        "langchain_project": settings.langchain_project,
        "langsmith_tracing": settings.langsmith_tracing,
        "langchain_endpoint": settings.langchain_endpoint,
    }

app.mount("/mcp", mcp_app)