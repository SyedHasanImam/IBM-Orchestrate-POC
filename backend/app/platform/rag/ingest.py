import threading

import chromadb
from langchain.embeddings import init_embeddings
from langchain_chroma import Chroma

from app.core.config import LLM_TIMEOUT_SECONDS, PROJECT_ROOT, settings
from app.platform.rag.chunking import chunk_text
from app.platform.rag.loader import load_compliance_documents

COLLECTION_NAME = "compliance_docs"

_client_lock = threading.Lock()
_client: chromadb.ClientAPI | None = None


def _embeddings():
    provider, _, model_name = settings.embedding_model.partition(":")
    return init_embeddings(
        model_name,
        provider=provider,
        request_options={"timeout": LLM_TIMEOUT_SECONDS},
    )


def _get_chroma_client() -> chromadb.ClientAPI:
    """A single process-wide PersistentClient, built once. Constructing a
    fresh PersistentClient against the same directory from concurrent
    threads (as happens when the compliance-checking agent calls
    search_compliance_kb multiple times in one turn — LangGraph's ToolNode
    runs those calls concurrently) races on chromadb's internal shared-client
    bookkeeping and corrupts it. Reusing one client avoids that entirely."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = chromadb.PersistentClient(
                    path=str(PROJECT_ROOT / settings.chroma_persist_dir)
                )
    return _client


def get_compliance_vector_store() -> Chroma:
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=_embeddings(),
        client=_get_chroma_client(),
    )


def ingest_compliance_documents() -> int:
    """(Re)ingest the compliance knowledge base from scratch. Idempotent —
    safe to call repeatedly; always drops and rebuilds the collection rather
    than diffing/upserting, since there are only 12 short documents total."""
    vector_store = get_compliance_vector_store()
    vector_store.delete_collection()
    vector_store = get_compliance_vector_store()

    documents = load_compliance_documents()
    ids = [f"{doc.metadata['source']}::{doc.metadata['title']}" for doc in documents]
    vector_store.add_documents(documents, ids=ids)
    return len(documents)


def get_instance_vector_store(instance_id: int) -> Chroma:
    """Each agent instance gets its own Chroma collection — Knowledge is
    instance-level, not shared, so one instance's uploaded documents never
    leak into another's retrieval."""
    return Chroma(
        collection_name=f"agent_instance_{instance_id}",
        embedding_function=_embeddings(),
        client=_get_chroma_client(),
    )


def ingest_document_for_instance(
    instance_id: int, filename: str, text: str, effective_date: str | None = None
) -> list[str]:
    """Chunk and embed one uploaded document into an instance's collection.
    effective_date (if given) is stamped onto every chunk's metadata so
    search_compliance_kb can surface it alongside a citation — otherwise a
    stale regulatory clause looks identical to a current one. Returns the
    chunk ids that were written, so the caller can persist them for later
    deletion."""
    vector_store = get_instance_vector_store(instance_id)
    documents = chunk_text(filename, text)
    if effective_date:
        for doc in documents:
            doc.metadata["effective_date"] = effective_date
    ids = [f"{filename}::{doc.metadata['title']}" for doc in documents]
    vector_store.add_documents(documents, ids=ids)
    return ids


def delete_document_from_instance(instance_id: int, chunk_ids: list[str]) -> None:
    vector_store = get_instance_vector_store(instance_id)
    vector_store.delete(ids=chunk_ids)
