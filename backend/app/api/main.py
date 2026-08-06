import uuid
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.checkpoint.postgres import PostgresSaver
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
    ChatDecisionRequest,
    ChatRequest,
    ChatResponse,
    CreateAgentInstanceRequest,
    DataSourceStatusOut,
    ExtractionWarningOut,
    HoldingsSnapshot,
    HomeChatDecisionRequest,
    PendingApprovalOut,
    ReconciliationDataOut,
    TemplateDetail,
    TemplateNodeSummary,
    ToolInfo,
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
from app.platform.runtime.loader import (
    list_registered_workflows,
    load_workflow_config,
    register_workflow,
)
from app.platform.runtime.report_tool import (
    GENERATE_REPORT_TOOL_NAME,
    get_pending_report,
    submit_report_decision,
    workflow_tool_names,
)
from app.platform.runtime.supervisor import (
    build_chat_supervisor,
    collaborator_name,
    extract_final_answer,
    extract_routed_to,
    resolve_mention,
)
from app.platform.tools.data_sources import required_data_sources
from app.platform.tools.registry import TOOL_REGISTRY

WORKFLOW_YAML_PATHS: list[Path] = [
    TRUSTEE_COMPLIANCE_WORKFLOW_YAML_PATH,
    STOCK_RECONCILIATION_WORKFLOW_YAML_PATH,
]


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


def _generate_report_called(new_messages: list) -> bool:
    """Whether generate_report actually ran during this turn's new
    messages — not just whether *some* report is sitting pending from a
    previous, unrelated turn. Without this check, asking an unrelated
    question while an old report is still awaiting a decision would
    silently replace the answer with that stale approval card again."""
    return any(
        isinstance(m, ToolMessage) and m.name == GENERATE_REPORT_TOOL_NAME
        for m in new_messages
    )


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
    if "extra_tools" in fields:
        unknown = set(fields["extra_tools"]) - TOOL_REGISTRY.keys()
        if unknown:
            raise HTTPException(
                status_code=400, detail=f"Unknown tool(s): {sorted(unknown)}"
            )
    if "collaborator_ids" in fields:
        collaborator_ids = fields["collaborator_ids"]
        if agent_id in collaborator_ids:
            raise HTTPException(status_code=400, detail="An agent cannot collaborate with itself.")
        missing = [cid for cid in collaborator_ids if get_instance(cid) is None]
        if missing:
            raise HTTPException(
                status_code=400, detail=f"Unknown agent instance(s): {sorted(missing)}"
            )
    row = update_instance(agent_id, **fields)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent instance: {agent_id}")
    return AgentInstance(**row)


@app.get("/tools", response_model=list[ToolInfo])
def list_tools() -> list[ToolInfo]:
    """Every tool available to be added to an agent via the Toolset tab's
    Add tool button — not just what a given template already uses."""
    return [
        ToolInfo(name=name, description=tool.description or "")
        for name, tool in sorted(TOOL_REGISTRY.items())
    ]


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


def _get_agent_or_404(agent_id: int) -> None:
    if get_instance(agent_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent instance: {agent_id}")


@app.get("/agents/{agent_id}/data-sources", response_model=list[DataSourceStatusOut])
def get_agent_data_sources(agent_id: int) -> list[DataSourceStatusOut]:
    """Which documents this agent currently needs uploaded — computed from
    its template's own tools plus whatever's been added via Add Tool, so a
    newly added tool's upload slot shows up here without any frontend code
    change. Backs the Knowledge tab's generic "Upload Documents" section."""
    instance = get_instance(agent_id)
    if instance is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent instance: {agent_id}")

    workflow_config = _get_workflow_config(instance["template_name"])
    tool_names = workflow_tool_names(workflow_config) | set(instance.get("extra_tools") or [])

    result = []
    for spec in required_data_sources(tool_names):
        if spec.kind == "holdings":
            holdings = instance.get("holdings_snapshot") or []
            result.append(
                DataSourceStatusOut(
                    key=spec.key,
                    label=spec.label,
                    description=spec.description,
                    required=spec.required,
                    kind=spec.kind,
                    accept=list(spec.accept),
                    filename=instance.get("holdings_filename"),
                    uploaded_at=instance.get("holdings_uploaded_at"),
                    count=len(holdings),
                    warnings=[
                        ExtractionWarningOut(**w) for w in (instance.get("holdings_warnings") or [])
                    ],
                )
            )
        else:
            inputs = instance.get("reconciliation_inputs") or {}
            slot = inputs.get(spec.key) or {}
            result.append(
                DataSourceStatusOut(
                    key=spec.key,
                    label=spec.label,
                    description=spec.description,
                    required=spec.required,
                    kind=spec.kind,
                    accept=list(spec.accept),
                    filename=slot.get("filename"),
                    uploaded_at=slot.get("uploaded_at"),
                    count=len(slot.get("rows", [])),
                    warnings=[
                        ExtractionWarningOut(source=spec.key, **w) for w in slot.get("warnings", [])
                    ],
                )
            )
    return result


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
async def upload_agent_document(
    agent_id: int, file: UploadFile, effective_date: str | None = Form(None)
) -> AgentDocument:
    _get_agent_or_404(agent_id)
    filename = file.filename or "untitled.txt"
    if not filename.lower().endswith(SUPPORTED_DOCUMENT_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type — knowledge documents must be one of {SUPPORTED_DOCUMENT_EXTENSIONS}.",
        )
    if effective_date:
        try:
            date.fromisoformat(effective_date)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="effective_date must be an ISO date (YYYY-MM-DD)."
            )
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 text.")

    # Re-uploading the same filename supersedes the prior version rather
    # than leaving both versions' chunks coexisting in the vector store —
    # otherwise a stale and a current version of the same document could
    # both surface from the same search_compliance_kb query.
    existing = instance_documents.find_document_by_filename(agent_id, filename)
    if existing is not None:
        instance_documents.delete_document(existing["id"])
        delete_document_from_instance(agent_id, existing["chunk_ids"])

    chunk_ids = ingest_document_for_instance(agent_id, filename, text, effective_date)
    row = instance_documents.create_document(
        instance_id=agent_id,
        filename=filename,
        chunk_ids=chunk_ids,
        effective_date=effective_date,
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

    # Add Agent collaborators (a fixed, build-time roster — the Toolset
    # tab's "Add agent") — only instances that still exist and are actually
    # deployed count, so a deleted or since-undeployed collaborator just
    # quietly drops out rather than erroring. Any dropped id stays in
    # collaborator_ids untouched; it's the chat-time roster that's filtered,
    # not the stored configuration.
    collaborator_instances = [
        row
        for row in (get_instance(cid) for cid in instance.get("collaborator_ids") or [])
        if row is not None and row["status"] == "deployed"
    ]

    if collaborator_instances:
        # This agent + its fixed collaborators, routed the same way the
        # homepage's multi-agent chat routes across its own (dynamic)
        # roster — same building block, just a fixed roster instead of a
        # runtime picker. This is what lets one agent absorb several
        # narrower agents' jobs behind a single description, so the
        # *homepage's* supervisor has one lean description to route on
        # instead of many overlapping ones.
        roster = [instance, *collaborator_instances]
        agent = build_chat_supervisor(roster, app.state.workflow_configs, app.state.checkpointer)
        config = {
            "configurable": {"thread_id": thread_id},
            "run_name": "agent-collaborator-chat",
            "callbacks": [get_langfuse_handler()],
        }

        before_count = len(agent.get_state(config).values.get("messages", []))
        result = agent.invoke(
            {"messages": [HumanMessage(content=body.message)]}, config=config
        )

        collaborator_names = {collaborator_name(i["id"]) for i in roster}
        routed_to_name = extract_routed_to(result["messages"])
        matched = next(
            (i for i in roster if collaborator_name(i["id"]) == routed_to_name), instance
        )

        if _generate_report_called(result["messages"][before_count:]):
            pending = get_pending_report(
                matched["id"], app.state.workflow_configs[matched["template_name"]],
                app.state.checkpointer,
            )
            if pending:
                return ChatResponse(
                    thread_id=thread_id,
                    message="",
                    pending_approval=PendingApprovalOut(agent_id=matched["id"], **pending),
                )

        return ChatResponse(
            thread_id=thread_id,
            message=extract_final_answer(result["messages"], collaborator_names),
            routed_to=matched["display_name"],
        )

    # No collaborators — the original, simpler single-agent path, entirely
    # unchanged from before Add Agent existed.
    workflow_config = _get_workflow_config(instance["template_name"])
    agent = build_agent_preview_chat(instance, workflow_config, app.state.checkpointer)
    config = {
        "configurable": {"thread_id": thread_id},
        "run_name": "agent-preview-chat",
        "callbacks": [get_langfuse_handler()],
    }

    before_count = len(agent.get_state(config).values.get("messages", []))
    result = agent.invoke(
        {"messages": [HumanMessage(content=body.message)]}, config=config
    )

    if _generate_report_called(result["messages"][before_count:]):
        pending = get_pending_report(agent_id, workflow_config, app.state.checkpointer)
        if pending:
            return ChatResponse(
                thread_id=thread_id,
                message="",
                pending_approval=PendingApprovalOut(agent_id=agent_id, **pending),
            )

    return ChatResponse(
        thread_id=thread_id,
        message=extract_text(result["messages"][-1]),
        routed_to=None,
    )


@app.post("/agents/{agent_id}/chat/decision", response_model=ChatResponse)
def submit_agent_chat_decision(agent_id: int, body: ChatDecisionRequest) -> ChatResponse:
    """Approves/rejects a pending report by resuming its report pipeline
    directly (report_tool.submit_report_decision) — independent of this
    chat's own conversation state, so the same function backs both this
    endpoint and the homepage chat's /chat/decision below.

    body.agent_id lets this resolve to a *collaborator's* report (Add
    Agent) rather than always this URL's own agent_id — defaults to the
    URL's agent_id when omitted, so callers that predate Add Agent are
    unaffected."""
    target_id = body.agent_id if body.agent_id is not None else agent_id
    instance = get_instance(target_id)
    if instance is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent instance: {target_id}")

    workflow_config = _get_workflow_config(instance["template_name"])
    result = submit_report_decision(
        target_id,
        workflow_config,
        app.state.checkpointer,
        decision=body.decision,
        actor=body.actor,
        comment=body.comment,
    )
    return ChatResponse(
        thread_id=body.thread_id,
        message=(
            f"Report {result['decision']}. Audit log id: {result['audit_log_id']}."
            f"\n\n{result['report']}"
        ),
    )


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    thread_id = body.thread_id or f"chat-{uuid.uuid4()}"
    selected_instances = [
        row
        for row in list_instances()
        if row["status"] == "deployed" and row.get("included_in_chat")
    ]

    # "@AgentName ..." addresses that one included agent directly instead
    # of leaving it to the supervisor's routing guess (see
    # supervisor.resolve_mention) — a cheaper alternative to a fixed
    # collaborator roster. Runs that agent's own standalone chat (same as
    # its own page), on a thread scoped to this chat + that agent, so an
    # explicit mention never depends on — or gets overridden by — the
    # supervisor's own judgment.
    mentioned_instance, mention_message = resolve_mention(body.message, selected_instances)
    if mentioned_instance is not None:
        workflow_config = app.state.workflow_configs[mentioned_instance["template_name"]]
        agent = build_agent_preview_chat(mentioned_instance, workflow_config, app.state.checkpointer)
        mention_config = {
            "configurable": {"thread_id": f"{thread_id}::mention::{mentioned_instance['id']}"},
            "run_name": "chat-mention",
            "callbacks": [get_langfuse_handler()],
        }
        before_count = len(agent.get_state(mention_config).values.get("messages", []))
        result = agent.invoke(
            {"messages": [HumanMessage(content=mention_message)]}, config=mention_config
        )
        if _generate_report_called(result["messages"][before_count:]):
            pending = get_pending_report(
                mentioned_instance["id"], workflow_config, app.state.checkpointer
            )
            if pending:
                return ChatResponse(
                    thread_id=thread_id,
                    message="",
                    pending_approval=PendingApprovalOut(agent_id=mentioned_instance["id"], **pending),
                )
        return ChatResponse(
            thread_id=thread_id,
            message=extract_text(result["messages"][-1]),
            routed_to=mentioned_instance["display_name"],
        )

    supervisor = build_chat_supervisor(
        selected_instances, app.state.workflow_configs, app.state.checkpointer
    )
    config = {
        "configurable": {"thread_id": thread_id},
        "run_name": "chat-supervisor",
        "callbacks": [get_langfuse_handler()],
    }

    before_count = len(supervisor.get_state(config).values.get("messages", []))
    result = supervisor.invoke(
        {"messages": [HumanMessage(content=body.message)]}, config=config
    )

    collaborator_names = {collaborator_name(i["id"]) for i in selected_instances}
    routed_to_name = extract_routed_to(result["messages"])
    matched = next(
        (i for i in selected_instances if collaborator_name(i["id"]) == routed_to_name),
        None,
    )

    if matched and _generate_report_called(result["messages"][before_count:]):
        pending = get_pending_report(
            matched["id"], app.state.workflow_configs[matched["template_name"]], app.state.checkpointer
        )
        if pending:
            return ChatResponse(
                thread_id=thread_id,
                message="",
                pending_approval=PendingApprovalOut(agent_id=matched["id"], **pending),
            )

    return ChatResponse(
        thread_id=thread_id,
        message=extract_final_answer(result["messages"], collaborator_names),
        routed_to=matched["display_name"] if matched else routed_to_name,
    )


@app.post("/chat/decision", response_model=ChatResponse)
def submit_chat_decision(body: HomeChatDecisionRequest) -> ChatResponse:
    """Approves/rejects a report generated through the homepage's
    multi-agent chat — needs agent_id (unlike the per-agent decision
    endpoint) since more than one collaborator could be involved. Resumes
    the same report pipeline directly, same as the per-agent endpoint."""
    instance = get_instance(body.agent_id)
    if instance is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent instance: {body.agent_id}")

    workflow_config = _get_workflow_config(instance["template_name"])
    result = submit_report_decision(
        body.agent_id,
        workflow_config,
        app.state.checkpointer,
        decision=body.decision,
        actor=body.actor,
        comment=body.comment,
    )
    return ChatResponse(
        thread_id=body.thread_id,
        message=(
            f"Report {result['decision']}. Audit log id: {result['audit_log_id']}."
            f"\n\n{result['report']}"
        ),
    )
