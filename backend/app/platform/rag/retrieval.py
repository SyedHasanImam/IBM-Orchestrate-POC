from langchain_core.tools import tool

from app.platform.rag.ingest import get_compliance_vector_store


@tool
def search_compliance_kb(query: str) -> list[dict]:
    """Search the fund's compliance knowledge base — the investment mandate
    (trust deed clauses on exposure limits, Shariah restrictions, liquidity,
    and equity allocation) and SECP regulatory excerpts — for text relevant
    to a compliance question. Returns the matching clause/excerpt title,
    source document, and full text for each result, so findings can be
    cited accurately.
    """
    vector_store = get_compliance_vector_store()
    results = vector_store.similarity_search(query, k=3)
    return [
        {
            "title": doc.metadata["title"],
            "source": doc.metadata["source"],
            "text": doc.page_content,
        }
        for doc in results
    ]
