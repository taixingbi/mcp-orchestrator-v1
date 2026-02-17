## 🔄 `/orchestrator/stream-answer` — SSE Execution Flow

This endpoint provides a **streaming, reliability-first orchestration pipeline** for answering questions using SQL tools, RAG tools, or both.

It emits **Server-Sent Events (SSE)** so clients can observe each reasoning stage in real time.

---

### ✅ 1. Request Initialization

* The service **accepts or generates** a `request_id`.
* Immediately emits:

```json
{ "type": "request_id", "request_id": "<uuid>" }
```

This ID is propagated through:

* LangGraph runs
* MCP tool calls
* LangSmith traces
* Feedback API

---

### ✍️ 2. Rewrite Phase (Query Normalization)

Two-step rewrite ensures consistent retrieval and evaluation:

#### a. Deterministic rewrite

`rewrite_to_third_person()` converts:

```
"your experience" → "Taixing Bi’s experience"
"you" → "Taixing Bi"
```

This prevents ambiguity when querying personal knowledge collections.

#### b. LLM semantic rewrite

A lightweight LLM pass makes the query:

* clearer
* more specific
* retrieval-friendly
* evaluation-safe

SSE emission:

```json
{ "type": "rewrite", "text": "<rewritten question>" }
```

---

### 🧭 3. Routing Phase (Tool Selection)

Routing decides which knowledge system to activate.

#### Hard Rule (Deterministic Guardrail)

If `"taixing"` appears in either:

* original question **OR**
* rewritten question

➡ Force:

```
RAG
```

This guarantees personal-profile queries never hit SQL datasets.

#### Otherwise → LLM Router decides:

```
RAG | SQL | BOTH
```

SSE emission:

```json
{ "type": "route", "route": "SQL" }
```

---

### ⚙️ 4. Execution Phases

Execution always follows this **fixed order**:

```
SQL → RAG
```

(when BOTH are selected and configured)

This allows:

* SQL to compute structured facts first
* RAG to enrich with semantic context afterward

---

### 🧠 5. `run_graph()` — LangGraph Agent Execution

Each phase invokes `run_graph()` which:


#### a. Runs the reliability loop:

```
LLM → Tool Calls → Evidence → Judge → Retry (if needed)
```

#### b. Captures the **root LangSmith run_id**

This becomes:

```
agent_graph_run_id
```

Used later for:

* Observability
* Human feedback
* Trace debugging
* Evaluation datasets

---

### 📤 6. Final Answer Emission

After all phases complete:

```json
{
  "type": "answer",
  "text": "<final answer>",
  "agent_graph_run_id": "<optional>"
}
```

---

### 🏁 7. Completion or Failure Signal

Success:

```json
{ "type": "done" }
```

Failure:

```json
{ "type": "error", "message": "<reason>" }
```

---

## 📡 Event Stream Example

```
request_id  → trace identity established
rewrite     → normalized query
route       → execution plan chosen
state       → phase progress updates
answer      → final grounded response
done        → stream completed
```

---

## 🧩 Why This Architecture Exists

This flow is intentionally designed to solve common LLM production failures:

| Problem                    | Solution in This Pipeline                       |
| -------------------------- | ----------------------------------------------- |
| Hallucination              | Tool-grounded LangGraph loop + judge validation |
| Wrong data source          | Deterministic routing guardrails                |                  |
| Unobservable failures      | SSE phase visibility                            |
| Weak retrieval queries     | Dual-stage rewrite                              |
| User feedback disconnected | `agent_graph_run_id` links feedback → trace     |

---

## 🗺️ Simplified Sequence Diagram

```mermaid
sequenceDiagram
  participant Client
  participant API
  participant Rewrite
  participant Router
  participant Graph as LangGraph (run_graph)
  participant MCP as MCP Tool Server(s)
  participant Judge as AnswerJudge (agent_answer_judge)

  Client->>API: POST /orchestrator/stream-answer
  API-->>Client: SSE {type:"request_id"}

  API->>Rewrite: normalize question
  Rewrite-->>API: rewritten question
  API-->>Client: SSE {type:"rewrite"}

  API->>Router: decide RAG | SQL | BOTH
  Router-->>API: route
  API-->>Client: SSE {type:"route"}

  alt route = SQL
    API->>Graph: run_graph(phase="SQL")
    Graph->>MCP: tool calls (SQL tools)
    Graph->>Judge: agent_answer_judge
  else route = RAG
    API->>Graph: run_graph(phase="RAG")
    Graph->>MCP: tool calls (RAG tools)
    Graph->>Judge: agent_answer_judge
  else route = BOTH
    API->>Graph: run_graph(phase="SQL")
    Graph->>MCP: tool calls (SQL tools)
    Graph->>Judge: agent_answer_judge
    API->>Graph: run_graph(phase="RAG")
    Graph->>MCP: tool calls (RAG tools)
    Graph->>Judge: agent_answer_judge
  end

  API-->>Client: SSE {type:"answer", agent_graph_run_id?}
  API-->>Client: SSE {type:"done"}


---

This endpoint is the **primary production interface** for orchestrated LLM reasoning across structured (SQL) and unstructured (RAG) knowledge systems.
