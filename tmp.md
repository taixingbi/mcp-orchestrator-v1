

curl -s -X POST http://localhost:8000/orchestrator/stream-answer \
-H "Content-Type: application/json" \
-d '{
  "session_id": "123456",
  "request_id": "12345678",
  "question": "List 5 job titles in Ventura"
}'


curl -s -X POST http://localhost:8000/orchestrator/stream-answer \
-H "Content-Type: application/json" \
-d '{
  "session_id": "123456",
  "request_id": "12345678",
  "question": "what is your expected taixing compensation? ?"
}'

curl -s -X POST http://localhost:8000/orchestrator/stream-answer \
-H "Content-Type: application/json" \
-d '{
  "session_id": "123456",
  "request_id": "12345678",
  "question": "what weather in sf"
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