from fastapi.testclient import TestClient

from app.api.main import app
from app.platform.rag.ingest import get_instance_vector_store

TEMPLATE_NAME = "trustee_compliance_reporting"

SAMPLE_DOC = b"""### Single Issuer Exposure Limit

No more than 10% of net assets may be invested in a single issuer.

### Liquidity Requirement

At least 10% of net assets must be held in cash or near-cash instruments.
"""


def _create_instance(client: TestClient) -> int:
    resp = client.post(
        "/agents",
        json={
            "template_name": TEMPLATE_NAME,
            "display_name": "Doc Test Agent",
            "description": "Created by an automated test.",
        },
    )
    assert resp.status_code == 200
    return resp.json()["id"]


def test_upload_list_delete_document():
    with TestClient(app) as client:
        agent_id = _create_instance(client)
        try:
            upload_resp = client.post(
                f"/agents/{agent_id}/documents",
                files={"file": ("mandate_excerpt.md", SAMPLE_DOC, "text/markdown")},
            )
            assert upload_resp.status_code == 200
            document = upload_resp.json()
            assert document["chunk_count"] == 2
            assert document["filename"] == "mandate_excerpt.md"

            list_resp = client.get(f"/agents/{agent_id}/documents")
            assert list_resp.status_code == 200
            assert len(list_resp.json()) == 1

            vector_store = get_instance_vector_store(agent_id)
            results = vector_store.similarity_search("single issuer exposure limit", k=1)
            assert results
            assert "10%" in results[0].page_content

            delete_resp = client.delete(
                f"/agents/{agent_id}/documents/{document['id']}"
            )
            assert delete_resp.status_code == 200

            list_after_delete = client.get(f"/agents/{agent_id}/documents")
            assert list_after_delete.json() == []
        finally:
            get_instance_vector_store(agent_id).delete_collection()


def test_upload_rejects_unsupported_file_type():
    with TestClient(app) as client:
        agent_id = _create_instance(client)
        try:
            resp = client.post(
                f"/agents/{agent_id}/documents",
                files={"file": ("holdings.pdf", b"%PDF-1.4 ...", "application/pdf")},
            )
            assert resp.status_code == 400
        finally:
            get_instance_vector_store(agent_id).delete_collection()
