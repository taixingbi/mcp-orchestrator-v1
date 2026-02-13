```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```


### Run MCP HTTP Server
```bash
uvicorn main:app --reload --port 8000
```

### Health check:
```bash
curl http://127.0.0.1:8000/health
```

### Run MCP HTTP Server
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