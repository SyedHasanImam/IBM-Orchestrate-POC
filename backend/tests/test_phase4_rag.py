import pytest

from app.platform.rag.ingest import ingest_compliance_documents
from app.platform.rag.loader import load_compliance_documents
from app.platform.rag.retrieval import search_compliance_kb


@pytest.fixture(scope="module", autouse=True)
def ingested_kb():
    count = ingest_compliance_documents()
    assert count == 12
    yield


def test_loader_produces_12_chunks_7_clauses_5_excerpts():
    documents = load_compliance_documents()
    assert len(documents) == 12

    mandate_docs = [d for d in documents if d.metadata["source"] == "investment_mandate.md"]
    secp_docs = [d for d in documents if d.metadata["source"] == "secp_regulatory_excerpts.md"]
    assert len(mandate_docs) == 7
    assert len(secp_docs) == 5


@pytest.mark.parametrize(
    "topic,query,expected_title_substring",
    [
        (
            "single-issuer exposure",
            "What is the maximum exposure allowed to a single issuer or company?",
            "Clause 6.1",
        ),
        (
            "single-sector exposure",
            "What is the maximum exposure allowed to a single sector?",
            "Clause 6.2",
        ),
        (
            "Shariah compliance restriction",
            "Can the fund invest in the shares of a conventional (non-Islamic) bank?",
            "Clause 6.3",
        ),
        (
            "minimum liquidity requirement",
            "What is the minimum percentage of net assets the fund must keep in cash or near-cash instruments?",
            "Clause 7.1",
        ),
        (
            "minimum equity allocation",
            "What is the minimum percentage of net assets that must be invested in listed equity securities?",
            "Clause 5.1",
        ),
    ],
)
def test_search_compliance_kb_retrieves_correct_clause(
    topic, query, expected_title_substring
):
    results = search_compliance_kb.invoke({"query": query})
    titles = [r["title"] for r in results]
    assert any(expected_title_substring in title for title in titles), (
        f"topic={topic!r} query={query!r} expected {expected_title_substring!r} "
        f"in one of {titles!r}"
    )
