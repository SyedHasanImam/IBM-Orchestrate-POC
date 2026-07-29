import re

from langchain_core.documents import Document

SECTION_PATTERN = re.compile(r"^### (.+)$", re.MULTILINE)


def chunk_text(source: str, text: str) -> list[Document]:
    """Split into one chunk per `### ` heading, same convention as the fixed
    compliance knowledge base. Falls back to a single whole-document chunk
    when no headings are present, so plain uploaded notes still ingest."""
    parts = SECTION_PATTERN.split(text)
    if len(parts) > 1:
        return [
            Document(
                page_content=f"{heading}\n\n{body.strip()}",
                metadata={"source": source, "title": heading},
            )
            for heading, body in zip(parts[1::2], parts[2::2])
        ]
    return [Document(page_content=text.strip(), metadata={"source": source, "title": source})]
