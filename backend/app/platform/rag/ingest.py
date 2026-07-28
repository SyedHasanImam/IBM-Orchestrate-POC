import threading

import chromadb
from langchain.embeddings import init_embeddings
from langchain_chroma import Chroma

from app.core.config import LLM_TIMEOUT_SECONDS, PROJECT_ROOT, settings
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
