# IBM watsonx Orchestrate Replication POC

This project is a single-company proof of concept for an agent platform
inspired by IBM watsonx Orchestrate. The implemented use case is mutual fund
operations, with configurable agents for compliance reporting and securities
reconciliation.

## What is implemented

- YAML-defined agent workflow templates loaded by a reusable LangGraph runtime.
- LangChain agents using Google Gemini models for aggregation, compliance
  analysis, report drafting, and conversational assistance.
- Fixed-edge LangGraph pipelines with human approval gates and audit logging.
- Deterministic Python calculations for portfolio exposures, compliance
  BREACH/PASS checks, position matching, and reconciliation break
  classification.
- Chroma vector retrieval over compliance and regulatory documents.
- PostgreSQL persistence for agent instances, registry data, audit records, and
  LangGraph checkpoints.
- Excel and PDF holdings ingestion, plus Excel ingestion for reconciliation
  documents.
- FastAPI backend APIs.
- A React/Vite TypeScript web application and a Streamlit application.

The project does not implement NL-to-SQL, CSV ingestion, a standalone OCR
engine, token streaming, or chart-based dashboards.

## Workflows

### Monthly trustee compliance reporting

The workflow in
`backend/app/agents/trustee_compliance_reporting/workflow.yaml` runs:

1. Holdings aggregation
2. Compliance checking
3. Report generation
4. Human approval or rejection
5. Audit-log finalization

Exposure aggregation and the five compliance checks are performed
deterministically in Python. The LLM presents the resulting figures and
citations rather than deciding the regulatory verdict.

### Stock/position reconciliation

The workflow in
`backend/app/agents/stock_reconciliation/workflow.yaml`:

1. Reads the fund ledger and custodian statement
2. Matches positions and identifies breaks
3. Uses trade blotter and corporate-action data to classify explanations
4. Drafts a reconciliation report
5. Waits for human approval or rejection
6. Writes the final decision to the audit log

## Architecture

```text
React/Vite or Streamlit UI
             |
          FastAPI
             |
   LangChain agents and tools
             |
   LangGraph workflow runtime
       |                 |
   PostgreSQL         ChromaDB
 (state, audit,       (embeddings and
  registry, data)      similarity search)
```

The workflow factory is implemented in
`backend/app/platform/runtime/factory.py`. It builds a `StateGraph` from
validated YAML configuration, adds the configured nodes, connects them in
fixed order, and compiles the graph with a checkpoint saver.

Conversational chat uses a supervisor from `langgraph-supervisor` to route
questions to selected specialist agents. A leading `@AgentName` mention can
route a question directly to one agent.

## Technology stack

### Backend and orchestration

- Python 3.12+
- FastAPI and Uvicorn
- LangChain
- LangGraph
- `langgraph-supervisor`
- Pydantic
- `psycopg`
- Langfuse callbacks for observability

### Models and retrieval

- Google Gemini through `langchain-google-genai`
- Configurable aggregation, compliance, and reporting models
- Gemini embeddings through LangChain's embedding interface
- ChromaDB through `langchain-chroma`

The model names in `backend/.env.example` are:

- `google_genai:gemini-3.1-flash-lite` for aggregation
- `google_genai:gemini-3.5-flash` for compliance
- `google_genai:gemini-3.5-flash-lite` for reporting
- `google_genai:gemini-embedding-001` for embeddings

### Persistence

- PostgreSQL for application data and LangGraph checkpointing
- ChromaDB persistent local storage for vector collections

### Frontend

- React 19
- TypeScript
- Vite
- React Router
- Radix UI
- Lucide React
- React Markdown with `remark-gfm`
- Streamlit (separate UI)

## Data ingestion and RAG

Holdings uploads accept `.xlsx` and `.pdf`. Excel workbooks are parsed with
`openpyxl`; PDF bytes are sent to the configured multimodal model as a PDF
attachment. The extraction path is implemented in
`backend/app/platform/extraction/extract.py`.

Reconciliation inputs are `.xlsx` workbooks for the ledger, custodian
statement, trade blotter, and corporate-actions calendar. They use
deterministic workbook parsing followed by structured LLM column mapping.

Knowledge uploads accept `.md` and `.txt`. Text is chunked, embedded, and
stored in Chroma. The retrieval tool performs similarity search and returns up
to three matching clauses or excerpts with source and optional effective-date
metadata.

## Frontend capabilities

The React UI provides:

- Multi-agent chat with supervisor routing
- Direct `@AgentName` routing
- Per-agent preview chat
- Agent catalog search and template-based agent creation
- Agent deployment, editing, and deletion
- Toolset configuration
- Knowledge document upload and removal
- Holdings and reconciliation-data uploads
- Upload status, row counts, extraction warnings, and replacement actions
- Markdown report rendering
- Human report approval/rejection with reviewer and comment fields

The Streamlit UI provides report execution, draft report review, approval or
rejection, an agent catalog table, and routed chat.

## Repository layout

```text
backend/
  app/
    api/                 FastAPI routes
    agents/              YAML workflow templates
    platform/
      extraction/        Excel/PDF extraction
      rag/               Chunking, ingestion, and retrieval
      runtime/           LangGraph and chat runtime
      tools/             Deterministic domain tools
      audit/             Audit-log persistence
      instances/         Agent-instance persistence
  tests/                 Backend test suite

frontend/
  react_app/             React/Vite application
  streamlit_app/         Streamlit application

data/mock/               Sample holdings, reconciliation, and compliance data
```

## Running locally

### Backend

1. Install the Python dependencies from `pyproject.toml`.
2. Copy `backend/.env.example` to `backend/.env`.
3. Set the Google API key, model names, PostgreSQL URL, Langfuse values, and
   Chroma persistence directory.
4. Start the FastAPI application with Uvicorn using the repository's backend
   entry point.

### React frontend

```text
cd frontend/react_app
npm install
npm run dev
```

Configure the backend API URL using the frontend environment example.

### Tests

```text
pytest
```
