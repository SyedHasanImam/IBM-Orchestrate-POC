from fastapi.testclient import TestClient

from app.api.main import app
from app.core.config import DATA_DIR
from app.platform.rag.ingest import get_instance_vector_store

TEMPLATE_NAME = "trustee_compliance_reporting"
MANDATE_PATH = DATA_DIR / "mock" / "compliance_docs" / "investment_mandate.md"
MOCK_HOLDINGS_PATH = DATA_DIR / "mock" / "fund_holdings" / "fund_holdings_dataset.xlsx"


def _create_instance(client: TestClient) -> int:
    resp = client.post(
        "/agents",
        json={
            "template_name": TEMPLATE_NAME,
            "display_name": "Preview Chat Test Agent",
            "description": "Created by an automated test.",
        },
    )
    assert resp.status_code == 200
    return resp.json()["id"]


def test_preview_chat_honestly_reports_no_knowledge_yet():
    with TestClient(app) as client:
        agent_id = _create_instance(client)
        try:
            resp = client.post(
                f"/agents/{agent_id}/chat",
                json={"message": "What is the minimum liquidity requirement?"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["thread_id"]
            assert data["routed_to"] is None
            # No documents attached yet — should say so, not invent a number.
            assert "5%" not in data["message"]
        finally:
            get_instance_vector_store(agent_id).delete_collection()


def test_preview_chat_cites_the_instances_own_knowledge():
    with TestClient(app) as client:
        agent_id = _create_instance(client)
        try:
            upload_resp = client.post(
                f"/agents/{agent_id}/documents",
                files={
                    "file": (
                        "investment_mandate.md",
                        MANDATE_PATH.read_bytes(),
                        "text/markdown",
                    )
                },
            )
            assert upload_resp.status_code == 200

            resp = client.post(
                f"/agents/{agent_id}/chat",
                json={"message": "What is the minimum liquidity requirement?"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "5%" in data["message"] or "5 percent" in data["message"].lower()
            assert "7.1" in data["message"]
        finally:
            get_instance_vector_store(agent_id).delete_collection()


def test_preview_chat_can_answer_holdings_questions_once_attached():
    with TestClient(app) as client:
        agent_id = _create_instance(client)
        try:
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

            resp = client.post(
                f"/agents/{agent_id}/chat",
                json={
                    "message": "How many holding positions does the fund currently have?"
                },
            )
            assert resp.status_code == 200
            assert "22" in resp.json()["message"]
        finally:
            get_instance_vector_store(agent_id).delete_collection()


def test_preview_chat_404s_for_unknown_agent():
    with TestClient(app) as client:
        resp = client.post("/agents/999999999/chat", json={"message": "hello"})
        assert resp.status_code == 404
