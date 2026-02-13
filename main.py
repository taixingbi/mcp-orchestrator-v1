# main.py — MCP HTTP server exposing RAG tools
import contextlib
import json
from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from mcp.server import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from config import settings
from orchestrator import answer_query_sync, stream_answer_query

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
            question, tools_timeout_s=60.0, invoke_timeout_s=120.0
        )
    except Exception as e:
        sub = getattr(e, "exceptions", None)
        err = sub[0] if sub else e
        return f"Error: {type(err).__name__}: {err}"


@mcp.tool()
async def _sse_stream_answer(question: str) -> str:
    """Alias for answer_question. Returns the full answer text (same as answer_question)."""
    return await answer_question(question)


def _sse_stream_answer_gen(question: str):
    """Async generator for POST /stream-answer. Yields SSE events from stream_answer_query."""
    async def _gen():
        async for chunk in stream_answer_query(question):
            yield f"data: {json.dumps({'text': chunk})}\n\n"
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


@app.post("/stream-answer")
async def stream_answer(body: StreamAnswerBody):
    """Stream the agent's answer as Server-Sent Events. Body: {"question": "..."}."""
    return StreamingResponse(
        _sse_stream_answer_gen(body.question),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "mcp": settings.mcp_name,
        "version": settings.app_version,
        "LANGCHAIN_PROJECT": settings.langchain_project,
    }

app.mount("/mcp", mcp_app)