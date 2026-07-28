import psycopg
import pytest
from langgraph.types import Command

from app.agents.trustee_compliance_reporting import WORKFLOW_YAML_PATH
from app.core.config import settings
from app.platform.rag.ingest import ingest_compliance_documents
from app.platform.runtime.checkpointer import postgres_checkpointer
from app.platform.runtime.factory import build_workflow_from_config
from app.platform.runtime.loader import load_workflow_config


@pytest.fixture(scope="module", autouse=True)
def ingested_kb():
    ingest_compliance_documents()
    yield


def _fetch_audit_row(audit_log_id: int):
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT thread_id, agent_name, event_type, actor, payload "
                "FROM audit_log WHERE id = %s;",
                (audit_log_id,),
            )
            return cur.fetchone()


def test_pipeline_halts_for_approval_and_resumes_after_simulated_restart():
    thread_id = "phase6-test-approve"
    config = {"configurable": {"thread_id": thread_id}}
    workflow_config = load_workflow_config(WORKFLOW_YAML_PATH)

    with postgres_checkpointer() as checkpointer_a:
        pipeline_a = build_workflow_from_config(workflow_config, checkpointer_a)
        result_a = pipeline_a.invoke({}, config=config)

    assert "__interrupt__" in result_a
    interrupt_payload = result_a["__interrupt__"][0].value
    assert "BREACH" in interrupt_payload["report"].upper()

    # Simulate a process restart: an entirely separate connection/graph.
    with postgres_checkpointer() as checkpointer_b:
        pipeline_b = build_workflow_from_config(workflow_config, checkpointer_b)
        result_b = pipeline_b.invoke(
            Command(
                resume={
                    "decision": "approved",
                    "actor": "trustee_officer_1",
                    "comment": "Reviewed, breaches noted for follow-up.",
                }
            ),
            config=config,
        )

    assert "audit_log_id" in result_b
    row = _fetch_audit_row(result_b["audit_log_id"])
    assert row is not None
    row_thread_id, agent_name, event_type, actor, payload = row
    assert row_thread_id == thread_id
    assert agent_name == "trustee_compliance_reporting"
    assert event_type == "report_approved"
    assert actor == "trustee_officer_1"
    assert payload["comment"] == "Reviewed, breaches noted for follow-up."
    assert "BREACH" in payload["report"].upper()


def test_pipeline_records_rejection_decision():
    thread_id = "phase6-test-reject"
    config = {"configurable": {"thread_id": thread_id}}
    workflow_config = load_workflow_config(WORKFLOW_YAML_PATH)

    with postgres_checkpointer() as checkpointer_a:
        pipeline_a = build_workflow_from_config(workflow_config, checkpointer_a)
        result_a = pipeline_a.invoke({}, config=config)
    assert "__interrupt__" in result_a

    with postgres_checkpointer() as checkpointer_b:
        pipeline_b = build_workflow_from_config(workflow_config, checkpointer_b)
        result_b = pipeline_b.invoke(
            Command(
                resume={
                    "decision": "rejected",
                    "actor": "trustee_officer_2",
                    "comment": "Needs revision before trustee sign-off.",
                }
            ),
            config=config,
        )

    row = _fetch_audit_row(result_b["audit_log_id"])
    assert row is not None
    _, _, event_type, actor, payload = row
    assert event_type == "report_rejected"
    assert actor == "trustee_officer_2"
    assert payload["comment"] == "Needs revision before trustee sign-off."
