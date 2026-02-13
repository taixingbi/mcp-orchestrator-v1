# main.py — MCP HTTP server exposing RAG tools
import contextlib
import json
from pydantic import BaseModel
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
    Chunks are dicts: {type: 'rewrite'|'answer'|'error', text: '...'}."""
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