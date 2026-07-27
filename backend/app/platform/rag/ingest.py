from langchain.embeddings import init_embeddings
from langchain_chroma import Chroma

from app.core.config import LLM_TIMEOUT_SECONDS, PROJECT_ROOT, settings
from app.platform.rag.loader import load_compliance_documents

COLLECTION_NAME = "compliance_docs"


def _embeddings():
    provider, _, model_name = settings.embedding_model.partition(":")
    return init_embeddings(
        model_name,
        provider=provider,
        request_options={"timeout": LLM_TIMEOUT_SECONDS},
    )


def get_compliance_vector_store() -> Chroma:
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=_embeddings(),
        persist_directory=str(PROJECT_ROOT / settings.chroma_persist_dir),
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
