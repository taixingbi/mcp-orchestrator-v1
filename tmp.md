

curl -s -X POST http://localhost:8000/orchestrator/stream-answer \
-H "Content-Type: application/json" \
-d '{
  "session_id": "123456",
  "request_id": "12345678",
  "question": "List 2 job titles in Ventura"
}'


curl -s -X POST http://localhost:8000/orchestrator/stream-answer \
-H "Content-Type: application/json" \
-d '{
  "session_id": "123456",
  "request_id": "12345678",
  "question": "What is the your visa status? Do they require sponsorship?"
}'

# MCP RAG tool (answer_question routes to RAG for person/candidate questions like visa)
curl -s -X POST http://localhost:8000/mcp/ \
-H "Content-Type: application/json" \
-H "Accept: application/json, text/event-stream" \
-d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"answer_question","arguments":{"question":"What is your visa status? Do they require sponsorship?"}}}'


curl -s -X POST http://localhost:8000/orchestrator/stream-answer \
-H "Content-Type: application/json" \
-d '{
  "session_id": "123456",
  "request_id": "12345678",
  "question": "what weather in sf"
}'


```bash
curl -s -X POST http://localhost:8000/feedback \
  -H "Content-Type: application/json" \
  -d '{"run_id":"019c5f02-df39-7020-bd01-338bc081c855","rating":"thumbs_up"}'
```

curl -s -X POST http://localhost:8000/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "agent_graph_run_id": "019c5f37-a2f8-7a40-b300-ba7b8547f120",
    "rating": "thumbs_down",
    "feedback_type": "not_factual",
    "question": "List 5 job titles in Ventura",
    "comment": "Only returned 3 titles"
  }'





## mcp_tool_rag
Common HR Questions This Tool Can Answer

This tool is designed to respond to questions like:

“What is Taixing Bi’s background?”

“Does he need visa sponsorship?”

“What LLM experience does he have?”

“What companies has he worked for?”

“Is he more ML or infrastructure focused?”

“What is his experience with LangChain / RAG?”

“Is he suitable for a production AI engineering role?”

“What cloud and backend systems has he built?”

“Years of experience and seniority level?”

“Has he deployed systems at scale?”



## mcp_tool_sql
This tool answers questions about government-related job data, including:

Public-sector job roles and classifications

Salary ranges and compensation structures

Job descriptions, responsibilities, and requirements

Role comparisons across agencies or job families

Pay bands, levels, and seniority mapping

Labor-market insights derived from structured datasets

🚫 This tool does NOT contain or return any personal or candidate information, including Taixing Bi.
It operates only on institutional / dataset-driven information.




    async def llm_call(state: MessagesState):
        result = await llm.ainvoke(state["messages"])
        return {"messages": [result]}

    g = StateGraph(MessagesState)
    g.add_node("llm_call", llm_call)
    g.add_node("tool_node", tool_node)
    g.add_edge(START, "llm_call")
    g.add_conditional_edges("llm_call", _should_continue, ["tool_node", END])
    g.add_edge("tool_node", "llm_call")
    compiled = g.compile()


