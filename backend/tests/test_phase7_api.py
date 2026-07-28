from fastapi.testclient import TestClient

from app.api.main import app
from app.platform.rag.ingest import ingest_compliance_documents

ingest_compliance_documents()


def test_run_then_approve_full_cycle():
    with TestClient(app) as client:
        run_resp = client.post("/reports/trustee_compliance_reporting/run")
        assert run_resp.status_code == 200
        data = run_resp.json()
        assert data["thread_id"]
        assert "BREACH" in data["report"].upper()

        decision_resp = client.post(
            f"/reports/trustee_compliance_reporting/{data['thread_id']}/decision",
            json={
                "decision": "approved",
                "actor": "api_test_officer",
                "comment": "looks good",
            },
        )
        assert decision_resp.status_code == 200
        decision_data = decision_resp.json()
        assert decision_data["event_type"] == "report_approved"
        assert isinstance(decision_data["audit_log_id"], int)


def test_run_then_reject_full_cycle():
    with TestClient(app) as client:
        run_resp = client.post("/reports/trustee_compliance_reporting/run")
        assert run_resp.status_code == 200
        thread_id = run_resp.json()["thread_id"]

        decision_resp = client.post(
            f"/reports/trustee_compliance_reporting/{thread_id}/decision",
            json={
                "decision": "rejected",
                "actor": "api_test_officer_2",
                "comment": "needs revision",
            },
        )
        assert decision_resp.status_code == 200
        assert decision_resp.json()["event_type"] == "report_rejected"
