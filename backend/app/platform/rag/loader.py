from langchain_core.documents import Document

from app.core.config import DATA_DIR
from app.platform.rag.chunking import chunk_text

COMPLIANCE_DOCS_DIR = DATA_DIR / "mock" / "compliance_docs"
SOURCE_FILES = ["investment_mandate.md", "secp_regulatory_excerpts.md"]


def load_compliance_documents() -> list[Document]:
    """One chunk per clause/excerpt (12 total: 7 mandate clauses + 5 SECP
    excerpts) — deliberately no further splitting/chunking, since each
    source section is already short and self-contained."""
    documents = []
    for filename in SOURCE_FILES:
        path = COMPLIANCE_DOCS_DIR / filename
        documents.extend(chunk_text(filename, path.read_text(encoding="utf-8")))
    return documents
