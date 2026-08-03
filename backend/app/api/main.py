import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.agents.stock_reconciliation import (
    WORKFLOW_YAML_PATH as STOCK_RECONCILIATION_WORKFLOW_YAML_PATH,
)
from app.agents.trustee_compliance_reporting import (
    WORKFLOW_YAML_PATH as TRUSTEE_COMPLIANCE_WORKFLOW_YAML_PATH,
)
from app.api.schemas import (
    AgentDocument,
    AgentInstance,
    CatalogEntry,
    ChatRequest,
    ChatResponse,
    CreateAgentInstanceRequest,
    DecisionRequest,
    DecisionResponse,
    ExtractionWarningOut,
    HoldingsSnapshot,
    ReconciliationDataOut,
    RunReportResponse,
    TemplateDetail,
    TemplateNodeSummary,
    UpdateAgentInstanceRequest,
)
from app.core.config import DB_CONNECT_TIMEOUT_SECONDS, settings
from app.core.messages import extract_text
from app.core.observability import get_langfuse_handler
from app.platform.extraction.extract import (
    RECONCILIATION_DOCUMENT_TYPES,
    extract_holdings,
    extract_reconciliation_document,
)
from app.platform.instances import documents as instance_documents
from app.platform.instances.schema import ensure_instances_schema
from app.platform.instances.store import (
    create_instance,
    delete_instance,
    deploy_instance,
    get_instance,
    list_instances,
    set_holdings,
    set_reconciliation_input,
    update_instance,
)
from app.platform.rag.ingest import (
    delete_document_from_instance,
    get_instance_vector_store,
    ingest_document_for_instance,
)
from app.platform.runtime.agent_chat import build_agent_preview_chat
from app.platform.runtime.factory import build_workflow_from_config
from app.platform.runtime.loader import (
    list_registered_workflows,
    load_workflow_config,
    register_workflow,
)
from app.platform.runtime.supervisor import (
    build_chat_supervisor,
    collaborator_name,
    extract_final_answer,
    extract_routed_to,
)

WORKFLOW_YAML_PATHS: list[Path] = [
    TRUSTEE_COMPLIANCE_WORKFLOW_YAML_PATH,
    STOCK_RECONCILIATION_WORKFLOW_YAML_PATH,
]

# Only some workflows depend on an instance's uploaded holdings snapshot —
# gating /reports/run on it universally would wrongly block a different
# workflow (like reconciliation) that depends on its own data instead.
HOLDINGS_DEPENDENT_TOOLS = {"get_fund_holdings", "get_portfolio_exposure_summary"}
RECONCILIATION_DEPENDENT_TOOLS = {
    "get_fund_ledger",
    "get_custodian_statement",
    "get_trade_blotter",
    "get_corporate_actions",
    "match_positions",
}
# Trade blotter and corporate actions only help *explain* breaks — their
# absence just means fewer breaks get auto-explained, not that reconciliation
# can't run at all. Ledger and custodian statement are the two sides being
# compared, so both are mandatory.
RECONCILIATION_REQUIRED_DOCS = ("ledger", "custodian_statement")


def _workflow_tool_names(config) -> set[str]:
    return {
        tool_name
        for node in config.nodes
        if node.type == "llm_agent"
        for tool_name in node.tools
    }


def _workflow_requires_holdings(config) -> bool:
    return bool(_workflow_tool_names(config) & HOLDINGS_DEPENDENT_TOOLS)


def _workflow_requires_reconciliation_data(config) -> bool:
    return bool(_workflow_tool_names(config) & RECONCILIATION_DEPENDENT_TOOLS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = ConnectionPool(
        conninfo=settings.database_url,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
            "connect_timeout": DB_CONNECT_TIMEOUT_SECONDS,
        },
        min_size=1,
        max_size=5,
        open=False,
        # Neon (our free-tier cloud Postgres) silently closes connections
        # that sit idle for a while. Without this, a request can be handed
        # one of those already-dead connections and crash with a raw
        # "server closed the connection unexpectedly" error. This makes the
        # pool ping a connection before handing it out and transparently
        # swap in a fresh one if it's dead, instead of surfacing the crash.
        check=ConnectionPool.check_connection,
    )
    pool.open()
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()
    app.state.checkpointer = checkpointer

    ensure_instances_schema()

    app.state.workflow_configs = {}
    for yaml_path in WORKFLOW_YAML_PATHS:
        config = load_workflow_config(yaml_path)
        register_workflow(config)
        app.state.workflow_configs[config.name] = config

    yield
    pool.close()


app = FastAPI(title="Orchestrate POC API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # Local dev only — the React app runs on Vite's default port, on a
    # different origin than the FastAPI backend.
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_workflow_config(workflow_name: str):
    config = app.state.workflow_configs.get(workflow_name)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Unknown workflow: {workflow_name}")
    return config


@app.post(
    "/reports/{workflow_name}/{thread_id}/decision", response_model=DecisionResponse
)
def submit_decision(
    workflow_name: str, thread_id: str, body: DecisionRequest
) -> DecisionResponse:
    config = _get_workflow_config(workflow_name)
    pipeline = build_workflow_from_config(config, app.state.checkpointer)
    run_config = {"configurable": {"thread_id": thread_id}}

    result = pipeline.invoke(
        Command(
            resume={
                "decision": body.decision,
                "actor": body.actor,
                "comment": body.comment,
            }
        ),
        config=run_config,
    )
    if "audit_log_id" not in result:
        raise HTTPException(
            status_code=500, detail="Decision did not finalize as expected."
        )

    event_type = "report_approved" if body.decision == "approved" else "report_rejected"
    return DecisionResponse(audit_log_id=result["audit_log_id"], event_type=event_type)


@app.get("/catalog", response_model=list[CatalogEntry])
def list_catalog() -> list[CatalogEntry]:
    return [CatalogEntry(**row) for row in list_registered_workflows()]


@app.get("/templates/{template_name}", response_model=TemplateDetail)
def get_template(template_name: str) -> TemplateDetail:
    config = _get_workflow_config(template_name)  # 404s if unknown
    registry_row = next(
        row for row in list_registered_workflows() if row["name"] == template_name
    )
    llm_agent_nodes = [node for node in config.nodes if node.type == "llm_agent"]

    tools: list[str] = []
    for node in llm_agent_nodes:
        for tool_name in node.tools:
            if tool_name not in tools:
                tools.append(tool_name)

    return TemplateDetail(
        name=config.name,
        description=config.description,
        version=registry_row["version"],
        updated_at=registry_row["updated_at"],
        nodes=[TemplateNodeSummary(name=node.name, type=node.type) for node in llm_agent_nodes],
        tools=tools,
    )


@app.post("/agents", response_model=AgentInstance)
def create_agent(body: CreateAgentInstanceRequest) -> AgentInstance:
    _get_workflow_config(body.template_name)  # 404s if not a real template
    return AgentInstance(**create_instance(**body.model_dump()))


@app.get("/agents", response_model=list[AgentInstance])
def get_agents() -> list[AgentInstance]:
    return [AgentInstance(**row) for row in list_instances()]


@app.get("/agents/{agent_id}", response_model=AgentInstance)
def get_agent(agent_id: int) -> AgentInstance:
    row = get_instance(agent_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent instance: {agent_id}")
    return AgentInstance(**row)


@app.patch("/agents/{agent_id}", response_model=AgentInstance)
def patch_agent(agent_id: int, body: UpdateAgentInstanceRequest) -> AgentInstance:
    fields = body.model_dump(exclude_unset=True)
    row = update_instance(agent_id, **fields)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent instance: {agent_id}")
    return AgentInstance(**row)


@app.post("/agents/{agent_id}/deploy", response_model=AgentInstance)
def deploy_agent(agent_id: int) -> AgentInstance:
    row = deploy_instance(agent_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent instance: {agent_id}")
    return AgentInstance(**row)


@app.delete("/agents/{agent_id}", response_model=AgentInstance)
def delete_agent(agent_id: int) -> AgentInstance:
    row = delete_instance(agent_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent instance: {agent_id}")
    get_instance_vector_store(agent_id).delete_collection()
    return AgentInstance(**row)


@app.post("/agents/{agent_id}/reports/run", response_model=RunReportResponse)
def run_agent_report(agent_id: int) -> RunReportResponse:
    agent = get_instance(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent instance: {agent_id}")
    if agent["status"] != "deployed":
        raise HTTPException(
            status_code=400,
            detail="Agent must be deployed before it can generate reports.",
        )

    workflow_name = agent["template_name"]
    config = _get_workflow_config(workflow_name)
    if _workflow_requires_holdings(config) and not agent.get("holdings_snapshot"):
        raise HTTPException(
            status_code=400,
            detail="Upload this agent's holdings (Knowledge tab) before generating a report.",
        )
    if _workflow_requires_reconciliation_data(config):
        inputs = agent.get("reconciliation_inputs") or {}
        missing = [
            doc_type
            for doc_type in RECONCILIATION_REQUIRED_DOCS
            if not (inputs.get(doc_type) or {}).get("rows")
        ]
        if missing:
            missing_labels = [doc_type.replace("_", " ") for doc_type in missing]
            raise HTTPException(
                status_code=400,
                detail=(
                    "Upload this agent's "
                    + " and ".join(missing_labels)
                    + " (Knowledge tab) before generating a report."
                ),
            )

    thread_id = f"agent-{agent_id}-{uuid.uuid4()}"
    pipeline = build_workflow_from_config(config, app.state.checkpointer)
    run_config = {
        "configurable": {"thread_id": thread_id, "agent_instance_id": agent_id}
    }

    result = pipeline.invoke({}, config=run_config)
    if "__interrupt__" not in result:
        raise HTTPException(
            status_code=500,
            detail="Pipeline did not pause for approval as expected.",
        )

    interrupt_payload = result["__interrupt__"][0].value
    warnings = [ExtractionWarningOut(**w) for w in (agent.get("holdings_warnings") or [])]
    if _workflow_requires_reconciliation_data(config):
        inputs = agent.get("reconciliation_inputs") or {}
        for doc_type in RECONCILIATION_DOCUMENT_TYPES:
            for w in (inputs.get(doc_type) or {}).get("warnings", []):
                warnings.append(ExtractionWarningOut(source=doc_type, **w))

    return RunReportResponse(
        thread_id=thread_id,
        workflow_name=workflow_name,
        report=interrupt_payload["report"],
        message=interrupt_payload["message"],
        extraction_warnings=warnings,
    )


def _get_agent_or_404(agent_id: int) -> None:
    if get_instance(agent_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent instance: {agent_id}")


SUPPORTED_HOLDINGS_EXTENSIONS = (".xlsx", ".pdf")


@app.post("/agents/{agent_id}/holdings", response_model=HoldingsSnapshot)
async def upload_agent_holdings(agent_id: int, file: UploadFile) -> HoldingsSnapshot:
    _get_agent_or_404(agent_id)
    filename = file.filename or "holdings"
    if not filename.lower().endswith(SUPPORTED_HOLDINGS_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type — holdings must be one of {SUPPORTED_HOLDINGS_EXTENSIONS}.",
        )
    raw = await file.read()
    try:
        extraction = extract_holdings(filename, raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    holdings = [h.model_dump() for h in extraction.holdings]
    warnings = [w.model_dump() for w in extraction.warnings]
    row = set_holdings(agent_id, holdings=holdings, warnings=warnings, filename=filename)

    return HoldingsSnapshot(
        filename=row["holdings_filename"],
        uploaded_at=row["holdings_uploaded_at"],
        holdings_count=len(holdings),
        warnings=[ExtractionWarningOut(**w) for w in warnings],
    )


@app.get("/agents/{agent_id}/holdings", response_model=HoldingsSnapshot)
def get_agent_holdings(agent_id: int) -> HoldingsSnapshot:
    row = get_instance(agent_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent instance: {agent_id}")

    holdings = row.get("holdings_snapshot") or []
    warnings = row.get("holdings_warnings") or []
    return HoldingsSnapshot(
        filename=row.get("holdings_filename"),
        uploaded_at=row.get("holdings_uploaded_at"),
        holdings_count=len(holdings),
        warnings=[ExtractionWarningOut(**w) for w in warnings],
    )


@app.post(
    "/agents/{agent_id}/reconciliation-data/{doc_type}",
    response_model=ReconciliationDataOut,
)
async def upload_reconciliation_data(
    agent_id: int, doc_type: str, file: UploadFile
) -> ReconciliationDataOut:
    _get_agent_or_404(agent_id)
    if doc_type not in RECONCILIATION_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=404, detail=f"Unknown reconciliation document type: {doc_type}"
        )
    filename = file.filename or doc_type
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type for {doc_type} — must be .xlsx.",
        )
    raw = await file.read()
    try:
        extraction = extract_reconciliation_document(doc_type, filename, raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    rows = [r.model_dump() for r in extraction.rows]
    warnings = [w.model_dump() for w in extraction.warnings]
    row = set_reconciliation_input(
        agent_id, doc_type=doc_type, rows=rows, warnings=warnings, filename=filename
    )
    slot = row["reconciliation_inputs"][doc_type]
    return ReconciliationDataOut(
        doc_type=doc_type,
        filename=slot["filename"],
        uploaded_at=slot["uploaded_at"],
        row_count=len(rows),
        warnings=[ExtractionWarningOut(source=doc_type, **w) for w in warnings],
    )


@app.get(
    "/agents/{agent_id}/reconciliation-data", response_model=list[ReconciliationDataOut]
)
def get_reconciliation_data(agent_id: int) -> list[ReconciliationDataOut]:
    agent = get_instance(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent instance: {agent_id}")

    inputs = agent.get("reconciliation_inputs") or {}
    result = []
    for doc_type in RECONCILIATION_DOCUMENT_TYPES:
        slot = inputs.get(doc_type) or {}
        result.append(
            ReconciliationDataOut(
                doc_type=doc_type,
                filename=slot.get("filename"),
                uploaded_at=slot.get("uploaded_at"),
                row_count=len(slot.get("rows", [])),
                warnings=[
                    ExtractionWarningOut(source=doc_type, **w)
                    for w in slot.get("warnings", [])
                ],
            )
        )
    return result


SUPPORTED_DOCUMENT_EXTENSIONS = (".md", ".txt")


@app.post("/agents/{agent_id}/documents", response_model=AgentDocument)
async def upload_agent_document(agent_id: int, file: UploadFile) -> AgentDocument:
    _get_agent_or_404(agent_id)
    filename = file.filename or "untitled.txt"
    if not filename.lower().endswith(SUPPORTED_DOCUMENT_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type — knowledge documents must be one of {SUPPORTED_DOCUMENT_EXTENSIONS}.",
        )
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 text.")

    chunk_ids = ingest_document_for_instance(agent_id, filename, text)
    row = instance_documents.create_document(
        instance_id=agent_id, filename=filename, chunk_ids=chunk_ids
    )
    return AgentDocument(**row)


@app.get("/agents/{agent_id}/documents", response_model=list[AgentDocument])
def get_agent_documents(agent_id: int) -> list[AgentDocument]:
    _get_agent_or_404(agent_id)
    return [AgentDocument(**row) for row in instance_documents.list_documents(agent_id)]


@app.delete("/agents/{agent_id}/documents/{document_id}", response_model=AgentDocument)
def delete_agent_document(agent_id: int, document_id: int) -> AgentDocument:
    row = instance_documents.get_document(document_id)
    if row is None or row["instance_id"] != agent_id:
        raise HTTPException(status_code=404, detail=f"Unknown document: {document_id}")
    deleted = instance_documents.delete_document(document_id)
    delete_document_from_instance(agent_id, deleted["chunk_ids"])
    return AgentDocument(**deleted)


@app.post("/agents/{agent_id}/chat", response_model=ChatResponse)
def chat_with_agent(agent_id: int, body: ChatRequest) -> ChatResponse:
    instance = get_instance(agent_id)
    if instance is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent instance: {agent_id}")

    thread_id = body.thread_id or f"agent-{agent_id}-preview-{uuid.uuid4()}"
    workflow_config = _get_workflow_config(instance["template_name"])
    agent = build_agent_preview_chat(instance, workflow_config, app.state.checkpointer)
    config = {
        "configurable": {"thread_id": thread_id},
        "run_name": "agent-preview-chat",
        "callbacks": [get_langfuse_handler()],
    }

    result = agent.invoke(
        {"messages": [HumanMessage(content=body.message)]}, config=config
    )

    return ChatResponse(
        thread_id=thread_id,
        message=extract_text(result["messages"][-1]),
        routed_to=None,
    )


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    thread_id = body.thread_id or f"chat-{uuid.uuid4()}"
    selected_instances = [
        row
        for row in list_instances()
        if row["status"] == "deployed" and row.get("included_in_chat")
    ]
    supervisor = build_chat_supervisor(
        selected_instances, app.state.workflow_configs, app.state.checkpointer
    )
    config = {
        "configurable": {"thread_id": thread_id},
        "run_name": "chat-supervisor",
        "callbacks": [get_langfuse_handler()],
    }

    result = supervisor.invoke(
        {"messages": [HumanMessage(content=body.message)]}, config=config
    )

    collaborator_names = {collaborator_name(i["id"]) for i in selected_instances}
    routed_to = extract_routed_to(result["messages"])
    if routed_to:
        matched = next(
            (i for i in selected_instances if collaborator_name(i["id"]) == routed_to),
            None,
        )
        routed_to = matched["display_name"] if matched else routed_to

    return ChatResponse(
        thread_id=thread_id,
        message=extract_final_answer(result["messages"], collaborator_names),
        routed_to=routed_to,
    )
