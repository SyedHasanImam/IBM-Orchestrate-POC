from fastapi.testclient import TestClient

from app.api.main import app


def test_catalog_lists_registered_workflows():
    with TestClient(app) as client:
        resp = client.get("/catalog")
        assert resp.status_code == 200
        names = {entry["name"] for entry in resp.json()}
        assert "trustee_compliance_reporting" in names


def test_unknown_workflow_returns_404():
    with TestClient(app) as client:
        resp = client.post("/reports/not_a_real_workflow/run")
        assert resp.status_code == 404


def test_template_detail_lists_llm_agent_nodes_only():
    with TestClient(app) as client:
        resp = client.get("/templates/trustee_compliance_reporting")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "trustee_compliance_reporting"
        node_names = [node["name"] for node in data["nodes"]]
        assert node_names == ["aggregation", "compliance_check", "reporting"]
        assert all(node["type"] == "llm_agent" for node in data["nodes"])


def test_unknown_template_detail_returns_404():
    with TestClient(app) as client:
        resp = client.get("/templates/not_a_real_template")
        assert resp.status_code == 404
