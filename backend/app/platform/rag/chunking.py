import re

from langchain_core.documents import Document

SECTION_PATTERN = re.compile(r"^### (.+)$", re.MULTILINE)

# Sizing for the paragraph-based fallback below (documents without `### `
# headings — e.g. a real regulatory circular pasted in as plain prose).
# IBM's own RAG guidance recommends 10-20% overlap between adjacent chunks
# so a clause split across a chunk boundary doesn't lose context. The
# heading-based path above needs no such overlap: each heading is already
# one complete, self-contained clause, so there's no arbitrary boundary to
# begin with.
FALLBACK_CHUNK_CHARS = 1200
FALLBACK_OVERLAP_CHARS = 200


def _chunk_by_paragraphs(source: str, text: str) -> list[Document]:
    """Group paragraphs into ~FALLBACK_CHUNK_CHARS-sized chunks, carrying
    the tail of each chunk into the next as overlap. Used only when no
    `### ` heading structure is present, so a chunk boundary here is
    genuinely arbitrary (unlike the heading-based path)."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return [Document(page_content=text.strip(), metadata={"source": source, "title": source})]

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) > FALLBACK_CHUNK_CHARS and current:
            chunks.append(current)
            overlap = current[-FALLBACK_OVERLAP_CHARS:]
            current = f"{overlap}\n\n{paragraph}"
        else:
            current = candidate
    if current:
        chunks.append(current)

    if len(chunks) == 1:
        return [Document(page_content=chunks[0], metadata={"source": source, "title": source})]
    return [
        Document(
            page_content=chunk,
            metadata={"source": source, "title": f"{source} (part {i + 1}/{len(chunks)})"},
        )
        for i, chunk in enumerate(chunks)
    ]


def chunk_text(source: str, text: str) -> list[Document]:
    """Split into one chunk per `### ` heading, same convention as the fixed
    compliance knowledge base — each heading is already one complete,
    self-contained clause. Falls back to overlapping paragraph-based chunks
    (see _chunk_by_paragraphs) when no headings are present, so plain
    uploaded documents still get meaningful retrieval granularity instead of
    ingesting as one undifferentiated chunk."""
    parts = SECTION_PATTERN.split(text)
    if len(parts) > 1:
        return [
            Document(
                page_content=f"{heading}\n\n{body.strip()}",
                metadata={"source": source, "title": heading},
            )
            for heading, body in zip(parts[1::2], parts[2::2])
        ]
    return _chunk_by_paragraphs(source, text)
