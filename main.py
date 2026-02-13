# main.py — MCP HTTP server exposing RAG tools
import contextlib
import json
from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from mcp.server import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from config import settings
from orchestrator import stream_answer_query

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
    parts = []
    async for chunk in stream_answer_query(question):
        parts.append(chunk)
    return "".join(parts) if parts else ""


def _sse_stream_answer(question: str):
    """Async generator: yield SSE events for stream_answer_query (used by POST /stream-answer only)."""
    async def _gen():
        async for chunk in stream_answer_query(question):
            yield f"data: {json.dumps({'text': chunk})}\n\n"
    return _gen()


mcp_app = mcp.streamable_http_app()


@contextlib.asynccontextmanager
async def _lifespan(_app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(title=settings.mcp_name, version="0.1.0", lifespan=_lifespan)


class StreamAnswerBody(BaseModel):
    question: str


@app.post("/stream-answer")
async def stream_answer(body: StreamAnswerBody):
    """Stream the agent's answer as Server-Sent Events. Body: {"question": "..."}."""
    return StreamingResponse(
        _sse_stream_answer(body.question),
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