import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.agents.trustee_compliance_reporting import (
    WORKFLOW_YAML_PATH as TRUSTEE_COMPLIANCE_WORKFLOW_YAML_PATH,
)
from app.api.schemas import (
    CatalogEntry,
    ChatRequest,
    ChatResponse,
    DecisionRequest,
    DecisionResponse,
    RunReportResponse,
)
from app.core.config import DB_CONNECT_TIMEOUT_SECONDS, settings
from app.core.observability import get_langfuse_handler
from app.platform.runtime.factory import build_workflow_from_config
from app.platform.runtime.loader import (
    list_registered_workflows,
    load_workflow_config,
    register_workflow,
)
from app.platform.runtime.supervisor import (
    build_chat_supervisor,
    extract_final_answer,
    extract_routed_to,
)

WORKFLOW_YAML_PATHS: list[Path] = [
    TRUSTEE_COMPLIANCE_WORKFLOW_YAML_PATH,
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
    )
    pool.open()
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()
    app.state.checkpointer = checkpointer

    app.state.workflow_configs = {}
    for yaml_path in WORKFLOW_YAML_PATHS:
        config = load_workflow_config(yaml_path)
        register_workflow(config)
        app.state.workflow_configs[config.name] = config

    yield
    pool.close()


app = FastAPI(title="Fund Management Agent Platform API", lifespan=lifespan)

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


@app.post("/reports/{workflow_name}/run", response_model=RunReportResponse)
def run_report(workflow_name: str) -> RunReportResponse:
    config = _get_workflow_config(workflow_name)
    thread_id = f"{workflow_name}-{uuid.uuid4()}"
    pipeline = build_workflow_from_config(config, app.state.checkpointer)
    run_config = {"configurable": {"thread_id": thread_id}}

    result = pipeline.invoke({}, config=run_config)
    if "__interrupt__" not in result:
        raise HTTPException(
            status_code=500,
            detail="Pipeline did not pause for approval as expected.",
        )

    interrupt_payload = result["__interrupt__"][0].value
    return RunReportResponse(
        thread_id=thread_id,
        report=interrupt_payload["report"],
        message=interrupt_payload["message"],
    )


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


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    thread_id = body.thread_id or f"chat-{uuid.uuid4()}"
    supervisor = build_chat_supervisor(app.state.checkpointer)
    config = {
        "configurable": {"thread_id": thread_id},
        "run_name": "chat-supervisor",
        "callbacks": [get_langfuse_handler()],
    }

    result = supervisor.invoke(
        {"messages": [HumanMessage(content=body.message)]}, config=config
    )

    return ChatResponse(
        thread_id=thread_id,
        message=extract_final_answer(result["messages"]),
        routed_to=extract_routed_to(result["messages"]),
    )
