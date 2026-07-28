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
