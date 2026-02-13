# MCP Orchestrator

Runs SQL then RAG MCP tools in sequence and exposes an `answer_question` MCP tool plus a streaming HTTP endpoint.

## Setup

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Environment (.env)

| Variable | Description |
|----------|-------------|
| `MCP_TOOL_SQL_URL` | SQL MCP server URL |
| `MCP_TOOL_RAG_URL` | RAG MCP server URL |
| `OPENAI_API_KEY` | Required for LLM |
| `OPENAI_MODEL` | Model name (default: `gpt-4o-mini`) |
| `REWRITE_QUERY` | `true` to rewrite questions before SQL/RAG |
| `TOOLS_TIMEOUT_S` | MCP tools timeout (default: 60) |
| `INVOKE_TIMEOUT_S` | Agent invoke timeout (default: 120) |

## Run

```bash
uvicorn main:app --reload --port 8000
```

## Health

```bash
curl http://127.0.0.1:8000/health
```

## MCP tool (tools/call)

```bash
curl -s -X POST \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"answer_question","arguments":{"question":"List 5 job titles in Ventura"}},"id":1}' \
  http://localhost:8000/mcp/
```

## Stream answer (SSE)

Events are `{type: "rewrite"|"answer"|"error", text: "..."}`:

```bash
curl -N -sS "http://localhost:8000/stream-answer" \
  -H "Content-Type: application/json" \
  -d '{"question": "List 5 job titles in Ventura?"}'
```
