from fastapi.testclient import TestClient

from app.api.main import app
from app.core.config import DATA_DIR
from app.platform.rag.ingest import get_instance_vector_store

TEMPLATE_NAME = "trustee_compliance_reporting"
MOCK_HOLDINGS_PATH = DATA_DIR / "mock" / "fund_holdings" / "fund_holdings_dataset.xlsx"


def _create_instance(client: TestClient) -> int:
    resp = client.post(
        "/agents",
        json={
            "template_name": TEMPLATE_NAME,
            "display_name": "Holdings Test Agent",
            "description": "Created by an automated test.",
        },
    )
    assert resp.status_code == 200
    return resp.json()["id"]


def test_holdings_start_empty_then_reflect_upload():
    with TestClient(app) as client:
        agent_id = _create_instance(client)
        try:
            empty = client.get(f"/agents/{agent_id}/holdings")
            assert empty.status_code == 200
            assert empty.json()["holdings_count"] == 0
            assert empty.json()["filename"] is None

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
            data = upload_resp.json()
            assert data["holdings_count"] == 22
            assert data["filename"] == "fund_holdings_dataset.xlsx"
            assert data["warnings"] == []

            get_resp = client.get(f"/agents/{agent_id}/holdings")
            assert get_resp.json()["holdings_count"] == 22
        finally:
            get_instance_vector_store(agent_id).delete_collection()


def test_holdings_upload_rejects_unsupported_file_type():
    with TestClient(app) as client:
        agent_id = _create_instance(client)
        try:
            resp = client.post(
                f"/agents/{agent_id}/holdings",
                files={"file": ("holdings.md", b"not a spreadsheet", "text/markdown")},
            )
            assert resp.status_code == 400
        finally:
            get_instance_vector_store(agent_id).delete_collection()


def test_holdings_upload_404s_for_unknown_agent():
    with TestClient(app) as client:
        resp = client.post(
            "/agents/999999999/holdings",
            files={
                "file": (
                    "fund_holdings_dataset.xlsx",
                    MOCK_HOLDINGS_PATH.read_bytes(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert resp.status_code == 404
