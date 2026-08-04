from fastapi.testclient import TestClient

from app.api.main import app
from app.core.config import DATA_DIR

MOCK_HOLDINGS_PATH = DATA_DIR / "mock" / "fund_holdings" / "fund_holdings_dataset.xlsx"
COMPLIANCE_DOCS_DIR = DATA_DIR / "mock" / "compliance_docs"


def _create_test_agent(client: TestClient, display_name: str) -> int:
    create_resp = client.post(
        "/agents",
        json={
            "template_name": "trustee_compliance_reporting",
            "display_name": display_name,
            "description": "Created by an automated test.",
        },
    )
    assert create_resp.status_code == 200
    return create_resp.json()["id"]


def _attach_knowledge(client: TestClient, agent_id: int) -> None:
    for filename in ["investment_mandate.md", "secp_regulatory_excerpts.md"]:
        path = COMPLIANCE_DOCS_DIR / filename
        upload_resp = client.post(
            f"/agents/{agent_id}/documents",
            files={"file": (filename, path.read_bytes(), "text/markdown")},
        )
        assert upload_resp.status_code == 200


def _attach_holdings(client: TestClient, agent_id: int) -> None:
    upload_resp = client.post(
        f"/agents/{agent_id}/holdings",
        files={
            "file": (
                "fund_holdings_dataset.xlsx",
                MOCK_HOLDINGS_PATH.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert upload_resp.status_code == 200


def _deploy_test_agent(client: TestClient) -> int:
    """Create an agent from the trustee compliance template, attach the
    regulation documents (Knowledge) and a holdings snapshot upfront, then
    deploy it — reports run purely off what's already attached."""
    agent_id = _create_test_agent(client, "Phase 7 API Test Agent")
    _attach_knowledge(client, agent_id)
    _attach_holdings(client, agent_id)

    deploy_resp = client.post(f"/agents/{agent_id}/deploy")
    assert deploy_resp.status_code == 200
    return agent_id


def _latest_audit_event_type(agent_id: int) -> str:
    """The outer chat agent's final message is the LLM's own paraphrase of
    the generate_report tool's result — its exact wording isn't guaranteed
    (whether it literally says "approved"/"rejected", or even states an
    audit log id in a consistently parseable way), so decision correctness
    has to be checked against the actual audit log row, not the chat text.
    generate_report always resumes the pipeline on the same deterministic
    thread id (chat-report-{instance_id}), so that's a reliable lookup key
    independent of anything the LLM said."""
    import psycopg

    from app.core.config import settings

    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT event_type FROM audit_log WHERE thread_id = %s "
                "ORDER BY id DESC LIMIT 1;",
                (f"chat-report-{agent_id}",),
            )
            row = cur.fetchone()
            assert row is not None
            return row[0]


def test_chat_generate_report_then_approve_full_cycle():
    with TestClient(app) as client:
        agent_id = _deploy_test_agent(client)
        try:
            chat_resp = client.post(
                f"/agents/{agent_id}/chat",
                json={"message": "Please generate this month's compliance report."},
            )
            assert chat_resp.status_code == 200
            data = chat_resp.json()
            assert data["thread_id"]
            assert data["pending_approval"] is not None
            assert "BREACH" in data["pending_approval"]["report"].upper()

            decision_resp = client.post(
                f"/agents/{agent_id}/chat/decision",
                json={
                    "thread_id": data["thread_id"],
                    "decision": "approved",
                    "actor": "api_test_officer",
                    "comment": "looks good",
                },
            )
            assert decision_resp.status_code == 200
            decision_data = decision_resp.json()
            assert decision_data["pending_approval"] is None
            assert _latest_audit_event_type(agent_id) == "report_approved"
        finally:
            _cleanup_agent(agent_id)


def test_chat_generate_report_then_reject_full_cycle():
    with TestClient(app) as client:
        agent_id = _deploy_test_agent(client)
        try:
            chat_resp = client.post(
                f"/agents/{agent_id}/chat",
                json={"message": "Please generate this month's compliance report."},
            )
            assert chat_resp.status_code == 200
            data = chat_resp.json()
            assert data["pending_approval"] is not None

            decision_resp = client.post(
                f"/agents/{agent_id}/chat/decision",
                json={
                    "thread_id": data["thread_id"],
                    "decision": "rejected",
                    "actor": "api_test_officer_2",
                    "comment": "needs revision",
                },
            )
            assert decision_resp.status_code == 200
            assert _latest_audit_event_type(agent_id) == "report_rejected"
        finally:
            _cleanup_agent(agent_id)


def test_chat_generate_report_refuses_when_holdings_missing():
    with TestClient(app) as client:
        agent_id = _create_test_agent(client, "No Holdings Agent")
        _attach_knowledge(client, agent_id)
        client.post(f"/agents/{agent_id}/deploy")
        try:
            chat_resp = client.post(
                f"/agents/{agent_id}/chat",
                json={"message": "Please generate this month's compliance report."},
            )
            assert chat_resp.status_code == 200
            data = chat_resp.json()
            # No pipeline to pause — the tool itself refuses before running it.
            assert data["pending_approval"] is None
            assert "upload" in data["message"].lower() or "holdings" in data["message"].lower()
        finally:
            _cleanup_agent(agent_id)


def _cleanup_agent(agent_id: int):
    import psycopg

    from app.core.config import DB_CONNECT_TIMEOUT_SECONDS, settings
    from app.platform.rag.ingest import get_instance_vector_store

    get_instance_vector_store(agent_id).delete_collection()
    with psycopg.connect(
        settings.database_url, connect_timeout=DB_CONNECT_TIMEOUT_SECONDS
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM agent_instances WHERE id = %s;", (agent_id,))
        conn.commit()
