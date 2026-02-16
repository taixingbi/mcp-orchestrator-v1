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



  curl -s -X POST https://mcp-orchestrator-v1-qa.fly.dev/orchestrator/stream-answer \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "123456",
    "request_id": "12345678",
    "question": "what is taixing visa status?"
  }'


curl -s -X POST https://mcp-orchestrator-v1-qa.fly.dev/orchestrator/stream-answer \
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
    "question": "what is Taixing visa status?"
  }'