# MCP Orchestrator

Runs SQL then RAG MCP tools in sequence and exposes an `answer_question` (and `_sse_stream_answer`) MCP tool plus a streaming HTTP endpoint.

## Setup

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Set `MCP_TOOL_SQL_URL`, `MCP_TOOL_RAG_URL`, and `OPENAI_API_KEY` in `.env` as needed.

## Run

```bash
uvicorn main:app --reload --port 8000
```

## Health

```bash
curl http://127.0.0.1:8000/health
```

## MCP tool (tools/call)

Same request body for `answer_question` or `_sse_stream_answer`; both return the full answer text.

```bash
curl -s -X POST \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"answer_question","arguments":{"question":"List 5 job titles in Ventura"}},"id":1}' \
  http://localhost:8000/mcp/
```

```bash
curl -s -X POST \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"answer_question","arguments":{"question":"what is taixing visa status"}},"id":1}' \
  http://localhost:8000/mcp/
```

Using the alias `_sse_stream_answer` (same result):

```bash
curl -s -X POST \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"_sse_stream_answer","arguments":{"question":"List 5 job titles in Ventura"}},"id":1}' \
  http://localhost:8000/mcp/
```



## Stream answer (SSE)

`/stream-answer` is on the main app (not under `/mcp`):

```bash
curl -N -sS "http://localhost:8000/stream-answer" \
  -H "Content-Type: application/json" \
  -d '{"question":"what is taixing visa?"}'
```