"""Direct MCP tools/call via HTTP JSON-RPC (curl-style)."""
import os
from typing import Tuple

import httpx

# Tool names for RAG and SQL MCP servers
RAG_TOOL_NAME = "rag_query_with_chunks"
SQL_TOOL_NAME = "sql_query"


def get_server_configs() -> Tuple[dict, dict]:
    """Return (sql_servers, rag_servers) from env. Each may be empty."""
    sql_url = os.getenv("MCP_TOOL_SQL_URL", "").rstrip("/")
    rag_url = os.getenv("MCP_TOOL_RAG_URL", "").rstrip("/")
    sql_servers = {"tool_sql": {"transport": "http", "url": sql_url + "/"}} if sql_url else {}
    rag_servers = {"tool_rag": {"transport": "http", "url": rag_url + "/"}} if rag_url else {}
    return sql_servers, rag_servers


async def _mcp_tools_call(
    base_url: str,
    tool_name: str,
    arguments: dict,
    *,
    timeout_s: float = 60.0,
) -> dict:
    """Call MCP tools/call via HTTP JSON-RPC. Same as the curl examples."""
    url = (base_url or "").rstrip("/") + "/"
    if not url:
        raise ValueError("base_url must be set")
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
        "id": 1,
    }
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        r = await client.post(
            url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )
        r.raise_for_status()
        return r.json()


async def call_rag_tool(question: str, *, timeout_s: float = 60.0) -> dict:
    """Call RAG MCP tool (rag_query_with_chunks) via HTTP. Implements the RAG curl example."""
    url = os.getenv("MCP_TOOL_RAG_URL", "").strip()
    if not url:
        raise ValueError("MCP_TOOL_RAG_URL must be set")
    return await _mcp_tools_call(
        url, RAG_TOOL_NAME, {"question": question}, timeout_s=timeout_s
    )


async def call_sql_tool(question: str, *, timeout_s: float = 60.0) -> dict:
    """Call SQL MCP tool via HTTP. Implements the SQL curl example (tool name from SQL_TOOL_NAME)."""
    url = os.getenv("MCP_TOOL_SQL_URL", "").strip()
    if not url:
        raise ValueError("MCP_TOOL_SQL_URL must be set")
    return await _mcp_tools_call(
        url, SQL_TOOL_NAME, {"question": question}, timeout_s=timeout_s
    )
