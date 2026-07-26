import re
from pathlib import Path

from langchain_core.documents import Document

from app.core.config import DATA_DIR

COMPLIANCE_DOCS_DIR = DATA_DIR / "mock" / "compliance_docs"
SOURCE_FILES = ["investment_mandate.md", "secp_regulatory_excerpts.md"]

SECTION_PATTERN = re.compile(r"^### (.+)$", re.MULTILINE)


def _load_sections(path: Path) -> list[Document]:
    text = path.read_text(encoding="utf-8")
    parts = SECTION_PATTERN.split(text)
    return [
        Document(
            page_content=f"{heading}\n\n{body.strip()}",
            metadata={"source": path.name, "title": heading},
        )
        for heading, body in zip(parts[1::2], parts[2::2])
    ]


def load_compliance_documents() -> list[Document]:
    """One chunk per clause/excerpt (12 total: 7 mandate clauses + 5 SECP
    excerpts) — deliberately no further splitting/chunking, since each
    source section is already short and self-contained."""
    documents = []
    for filename in SOURCE_FILES:
        documents.extend(_load_sections(COMPLIANCE_DOCS_DIR / filename))
    return documents
