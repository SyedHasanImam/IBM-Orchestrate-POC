from langchain_core.tools import tool

from app.platform.rag.ingest import get_compliance_vector_store, get_instance_vector_store


def _search(vector_store, query: str) -> list[dict]:
    results = vector_store.similarity_search(query, k=3)
    return [
        {
            "title": doc.metadata["title"],
            "source": doc.metadata["source"],
            "text": doc.page_content,
            # Only set for documents uploaded with an effective date — lets
            # a citation be checked against how current it actually is,
            # rather than only when it happened to be uploaded.
            "effective_date": doc.metadata.get("effective_date"),
        }
        for doc in results
    ]


@tool
def search_compliance_kb(query: str) -> list[dict]:
    """Search the fund's compliance knowledge base — the investment mandate
    (trust deed clauses on exposure limits, Shariah restrictions, liquidity,
    and equity allocation) and SECP regulatory excerpts — for text relevant
    to a compliance question. Returns the matching clause/excerpt title,
    source document, full text, and effective date (if known) for each
    result, so findings can be cited accurately — check effective_date
    before treating a result as current.
    """
    return _search(get_compliance_vector_store(), query)


def make_search_compliance_kb_tool(instance_id: int):
    """Build a search_compliance_kb tool bound to one agent instance's own
    Knowledge documents (Stage 2), instead of the shared fixed KB — so a
    report only checks holdings against the regulatory documents that
    specific agent was configured with."""
    vector_store = get_instance_vector_store(instance_id)

    @tool
    def search_compliance_kb(query: str) -> list[dict]:
        """Search the fund's compliance knowledge base — the investment
        mandate (trust deed clauses on exposure limits, Shariah
        restrictions, liquidity, and equity allocation) and SECP regulatory
        excerpts — for text relevant to a compliance question. Returns the
        matching clause/excerpt title, source document, full text, and
        effective date (if known) for each result, so findings can be
        cited accurately — check effective_date before treating a result
        as current.
        """
        return _search(vector_store, query)

    return search_compliance_kb
