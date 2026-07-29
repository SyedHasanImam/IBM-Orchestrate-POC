from fastapi.testclient import TestClient

from app.api.main import app

TEMPLATE_NAME = "trustee_compliance_reporting"


def test_create_list_get_patch_deploy_agent_instance():
    with TestClient(app) as client:
        create_resp = client.post(
            "/agents",
            json={
                "template_name": TEMPLATE_NAME,
                "display_name": "Stage 2 Test Agent",
                "description": "Created by an automated test.",
            },
        )
        assert create_resp.status_code == 200
        instance = create_resp.json()
        assert instance["status"] == "draft"
        agent_id = instance["id"]

        list_resp = client.get("/agents")
        assert list_resp.status_code == 200
        assert any(row["id"] == agent_id for row in list_resp.json())

        get_resp = client.get(f"/agents/{agent_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["display_name"] == "Stage 2 Test Agent"

        patch_resp = client.patch(
            f"/agents/{agent_id}", json={"display_name": "Renamed Test Agent"}
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["display_name"] == "Renamed Test Agent"

        deploy_resp = client.post(f"/agents/{agent_id}/deploy")
        assert deploy_resp.status_code == 200
        assert deploy_resp.json()["status"] == "deployed"

        delete_resp = client.delete(f"/agents/{agent_id}")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["id"] == agent_id

        get_after_delete = client.get(f"/agents/{agent_id}")
        assert get_after_delete.status_code == 404


def test_create_agent_rejects_unknown_template():
    with TestClient(app) as client:
        resp = client.post(
            "/agents",
            json={"template_name": "not_a_real_template", "display_name": "x"},
        )
        assert resp.status_code == 404


def test_get_agent_404_for_unknown_id():
    with TestClient(app) as client:
        resp = client.get("/agents/999999999")
        assert resp.status_code == 404


def test_delete_agent_404_for_unknown_id():
    with TestClient(app) as client:
        resp = client.delete("/agents/999999999")
        assert resp.status_code == 404
