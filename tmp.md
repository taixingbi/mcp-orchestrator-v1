curl -s -X POST "http://localhost:8000/mcp/" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "answer_question",
      "arguments": {
        "question": "what is your current visa",
        "request_id": "12345678",
        "session_id": "123456"
      }
    }
  }'

curl -s -X POST http://localhost:8000/orchestrator/stream-answer \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "123456",
    "request_id": "12345678",
    "question": "what is your current visa"
  }'


curl -s -X POST https://mcp-orchestrator-v1-qa.fly.dev/orchestrator/stream-answer \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "123456",
    "request_id": "12345678",
    "question": "List 5 job titles in Ventura?"
  }'


  curl -s -X POST https://mcp-orchestrator-v1-qa.fly.dev/orchestrator/stream-answer \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "123456",
    "request_id": "12345678",
    "question": "what is taixing expected compensation?"
  }'



  curl -s -X POST https://mcp-orchestrator-v1-dev.fly.dev/orchestrator/stream-answer \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "123456",
    "request_id": "12345678",
    "question": "“What is your current work authorization?”"
  }'


curl -s -X POST https://mcp-orchestrator-v1-dev.fly.dev/orchestrator/stream-answer \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "123456",
    "request_id": "12345678",
    "question": "Which jurisdiction has the highest-paying job title?"
  }'


curl -s -X POST http://localhost:8000/orchestrator/stream-answer \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "123456",
    "request_id": "12345678",
    "question": "“What is your current work authorization?”"
  }'




  hunter@macbook-pro ~ %   curl -s -X POST https://mcp-orchestrator-v1-dev.fly.dev/orchestrator/stream-answer \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "123456",
    "request_id": "12345678",
    "question": "what is taixing expected compensation?"
  }'