import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.agents.trustee_compliance_reporting.pipeline import (
    build_compliance_report_pipeline,
)
from app.api.schemas import DecisionRequest, DecisionResponse, RunReportResponse
from app.core.config import DB_CONNECT_TIMEOUT_SECONDS, settings


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
    yield
    pool.close()


app = FastAPI(title="Trustee Compliance Reporting API", lifespan=lifespan)


@app.post("/reports/trustee-compliance/run", response_model=RunReportResponse)
def run_report() -> RunReportResponse:
    thread_id = f"trustee-compliance-{uuid.uuid4()}"
    pipeline = build_compliance_report_pipeline(app.state.checkpointer)
    config = {"configurable": {"thread_id": thread_id}}

    result = pipeline.invoke({}, config=config)
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
    "/reports/trustee-compliance/{thread_id}/decision", response_model=DecisionResponse
)
def submit_decision(thread_id: str, body: DecisionRequest) -> DecisionResponse:
    pipeline = build_compliance_report_pipeline(app.state.checkpointer)
    config = {"configurable": {"thread_id": thread_id}}

    result = pipeline.invoke(
        Command(
            resume={
                "decision": body.decision,
                "actor": body.actor,
                "comment": body.comment,
            }
        ),
        config=config,
    )
    if "audit_log_id" not in result:
        raise HTTPException(
            status_code=500, detail="Decision did not finalize as expected."
        )

    event_type = "report_approved" if body.decision == "approved" else "report_rejected"
    return DecisionResponse(audit_log_id=result["audit_log_id"], event_type=event_type)
