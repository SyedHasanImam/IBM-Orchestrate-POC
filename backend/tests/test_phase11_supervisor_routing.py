import uuid

from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage

from app.agents.trustee_compliance_reporting import (
    WORKFLOW_YAML_PATH as TRUSTEE_COMPLIANCE_WORKFLOW_YAML_PATH,
)
from app.api.main import app
from app.core.config import DATA_DIR
from app.platform.instances.store import get_instance
from app.platform.rag.ingest import get_instance_vector_store
from app.platform.runtime.checkpointer import postgres_checkpointer
from app.platform.runtime.loader import load_workflow_config
from app.platform.runtime.report_tool import get_pending_report, submit_report_decision
from app.platform.runtime.supervisor import (
    build_chat_supervisor,
    extract_final_answer,
    extract_routed_to,
)

MOCK_HOLDINGS_PATH = DATA_DIR / "mock" / "fund_holdings" / "fund_holdings_dataset.xlsx"
MOCK_LEDGER_PATH = DATA_DIR / "mock" / "fund_ledger" / "fund_ledger_dataset.xlsx"
MOCK_CUSTODIAN_PATH = (
    DATA_DIR / "mock" / "custodian_statements" / "custodian_statement_dataset.xlsx"
)
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _create_deployed_and_included(
    client: TestClient, template_name: str, display_name: str, description: str
) -> int:
    resp = client.post(
        "/agents",
        json={
            "template_name": template_name,
            "display_name": display_name,
            "description": description,
        },
    )
    assert resp.status_code == 200
    agent_id = resp.json()["id"]
    assert client.post(f"/agents/{agent_id}/deploy").status_code == 200
    assert (
        client.patch(f"/agents/{agent_id}", json={"included_in_chat": True}).status_code
        == 200
    )
    return agent_id


def test_chat_routes_between_two_included_agent_instances():
    """The homepage chat should route to whichever real deployed instance
    is a better fit — not to hardcoded pipeline roles — based on each
    instance's own description."""
    with TestClient(app) as client:
        compliance_id = _create_deployed_and_included(
            client,
            "trustee_compliance_reporting",
            "Compliance Test Agent",
            "Checks the fund's holdings against the investment mandate and "
            "SECP regulatory limits.",
        )
        reconciliation_id = _create_deployed_and_included(
            client,
            "stock_reconciliation",
            "Reconciliation Test Agent",
            "Reconciles the fund's ledger against the custodian's statement "
            "and explains any breaks found.",
        )
        try:
            upload = client.post(
                f"/agents/{compliance_id}/holdings",
                files={
                    "file": (
                        "fund_holdings_dataset.xlsx",
                        MOCK_HOLDINGS_PATH.read_bytes(),
                        XLSX_MIME,
                    )
                },
            )
            assert upload.status_code == 200
            for doc_type, path in [
                ("ledger", MOCK_LEDGER_PATH),
                ("custodian_statement", MOCK_CUSTODIAN_PATH),
            ]:
                upload = client.post(
                    f"/agents/{reconciliation_id}/reconciliation-data/{doc_type}",
                    files={"file": (path.name, path.read_bytes(), XLSX_MIME)},
                )
                assert upload.status_code == 200

            holdings_resp = client.post(
                "/chat",
                json={"message": "How many holding positions does the fund currently have?"},
            )
            assert holdings_resp.status_code == 200
            holdings_data = holdings_resp.json()
            assert holdings_data["routed_to"] == "Compliance Test Agent"
            assert "22" in holdings_data["message"]

            recon_resp = client.post(
                "/chat",
                json={
                    "message": (
                        "Are there any unexplained reconciliation breaks between "
                        "the ledger and custodian statement?"
                    )
                },
            )
            assert recon_resp.status_code == 200
            recon_data = recon_resp.json()
            assert recon_data["routed_to"] == "Reconciliation Test Agent"
            assert "OGDC" in recon_data["message"] or "Oil & Gas" in recon_data["message"]
        finally:
            client.delete(f"/agents/{compliance_id}")
            client.delete(f"/agents/{reconciliation_id}")
            get_instance_vector_store(compliance_id).delete_collection()
            get_instance_vector_store(reconciliation_id).delete_collection()


def test_no_agents_selected_falls_back_to_plain_chat():
    with postgres_checkpointer() as checkpointer:
        supervisor = build_chat_supervisor([], {}, checkpointer)
        result = supervisor.invoke(
            {"messages": [HumanMessage(content="What is the fund's largest holding?")]},
            config={"configurable": {"thread_id": f"phase11-empty-{uuid.uuid4()}"}},
        )

    assert extract_routed_to(result["messages"]) is None
    answer = extract_final_answer(result["messages"], collaborator_names=set()).lower()
    assert "no" in answer and ("agent" in answer or "configured" in answer)


def _latest_audit_event_type(agent_id: int) -> str:
    """Same lookup as test_phase7_api.py's helper — the report pipeline
    always resumes on the deterministic thread chat-report-{instance_id}
    regardless of which chat (this agent's own, or the homepage's
    multi-agent one) asked for it, so this is a reliable way to confirm the
    decision was actually recorded rather than trusting the LLM's own
    paraphrase of what happened."""
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


def test_chat_generate_report_through_homepage_supervisor_then_approve():
    """Regression test for the bug this was built to fix: generating and
    approving a report through the homepage's multi-agent chat used to
    silently fail to write the audit log, because approval relied on
    resuming the chat's own (rebuilt-per-request) supervisor graph. It's
    fixed by decoupling approval from any chat's graph entirely — this test
    would have failed against the old implementation.

    Builds the supervisor directly from just this test's own instance
    (rather than going through the real /chat endpoint, which pulls in
    *every* instance currently marked included_in_chat) so it can't
    accidentally route to, and write a decision against, one of this
    project's real agents — that happened once while writing this test."""
    with TestClient(app) as client:
        compliance_id = _create_deployed_and_included(
            client,
            "trustee_compliance_reporting",
            "Compliance Test Agent 3",
            "Checks the fund's holdings against the investment mandate and "
            "SECP regulatory limits.",
        )
        try:
            upload = client.post(
                f"/agents/{compliance_id}/holdings",
                files={
                    "file": (
                        "fund_holdings_dataset.xlsx",
                        MOCK_HOLDINGS_PATH.read_bytes(),
                        XLSX_MIME,
                    )
                },
            )
            assert upload.status_code == 200

            instance = get_instance(compliance_id)
            workflow_config = load_workflow_config(TRUSTEE_COMPLIANCE_WORKFLOW_YAML_PATH)
            with postgres_checkpointer() as checkpointer:
                supervisor = build_chat_supervisor(
                    [instance], {"trustee_compliance_reporting": workflow_config}, checkpointer
                )
                supervisor.invoke(
                    {
                        "messages": [
                            HumanMessage(content="Please generate this month's compliance report.")
                        ]
                    },
                    config={"configurable": {"thread_id": f"phase11-report-{uuid.uuid4()}"}},
                )

                pending = get_pending_report(compliance_id, workflow_config, checkpointer)
                assert pending is not None
                assert "BREACH" in pending["report"].upper()

                decision = submit_report_decision(
                    compliance_id,
                    workflow_config,
                    checkpointer,
                    decision="approved",
                    actor="supervisor_test_officer",
                    comment="looks good",
                )
            assert decision["decision"] == "approved"
            assert _latest_audit_event_type(compliance_id) == "report_approved"
        finally:
            client.delete(f"/agents/{compliance_id}")
            get_instance_vector_store(compliance_id).delete_collection()


def test_supervisor_never_generates_a_full_report():
    with TestClient(app) as client:
        compliance_id = _create_deployed_and_included(
            client,
            "trustee_compliance_reporting",
            "Compliance Test Agent 2",
            "Checks the fund's holdings against the investment mandate and "
            "SECP regulatory limits.",
        )
        try:
            upload = client.post(
                f"/agents/{compliance_id}/holdings",
                files={
                    "file": (
                        "fund_holdings_dataset.xlsx",
                        MOCK_HOLDINGS_PATH.read_bytes(),
                        XLSX_MIME,
                    )
                },
            )
            assert upload.status_code == 200

            resp = client.post(
                "/chat", json={"message": "How many holding positions does the fund have?"}
            )
            assert resp.status_code == 200
            # These only ever appear in the Reporting Agent's formatted output
            # — their absence confirms the chat path never touches report
            # generation.
            answer = resp.json()["message"].lower()
            assert "executive summary" not in answer
            assert "pending trustee review" not in answer
        finally:
            client.delete(f"/agents/{compliance_id}")
            get_instance_vector_store(compliance_id).delete_collection()
