"""Application settings loaded from environment."""

import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Settings from env (and .env)."""

    # App
    mcp_name: str = os.getenv("MCP_NAME", "mcp-orchestrator")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")

    # LangChain / LangSmith
    langchain_project: Optional[str] = os.getenv("LANGCHAIN_PROJECT")
    langchain_api_key: Optional[str] = os.getenv("LANGCHAIN_API_KEY")
    langchain_endpoint: Optional[str] = os.getenv("LANGCHAIN_ENDPOINT")
    langsmith_tracing: bool = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"

    # MCP tool URLs (no trailing slash in env; code adds / when needed)
    mcp_tool_sql_url: Optional[str] = os.getenv("MCP_TOOL_SQL_URL")
    mcp_tool_rag_url: Optional[str] = os.getenv("MCP_TOOL_RAG_URL")

    # OpenAI (used by orchestrator; often set by LangChain)
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Query rewriting (refine question before SQL/RAG)
    rewrite_query: bool = os.getenv("REWRITE_QUERY", "false").lower() == "true"

    # Default timeouts for MCP tool calls (seconds)
    tools_timeout_s: float = float(os.getenv("TOOLS_TIMEOUT_S", "60"))
    invoke_timeout_s: float = float(os.getenv("INVOKE_TIMEOUT_S", "120"))


settings = Settings()
