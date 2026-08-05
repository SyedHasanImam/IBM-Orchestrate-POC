import psycopg
from psycopg.rows import dict_row

from app.core.config import DB_CONNECT_TIMEOUT_SECONDS, settings


def _connect():
    return psycopg.connect(
        settings.database_url,
        connect_timeout=DB_CONNECT_TIMEOUT_SECONDS,
        row_factory=dict_row,
    )


def create_document(
    *,
    instance_id: int,
    filename: str,
    chunk_ids: list[str],
    effective_date: str | None = None,
) -> dict:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent_instance_documents
                    (instance_id, filename, chunk_count, chunk_ids, effective_date)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *;
                """,
                (instance_id, filename, len(chunk_ids), chunk_ids, effective_date),
            )
            row = cur.fetchone()
        conn.commit()
    return row


def find_document_by_filename(instance_id: int, filename: str) -> dict | None:
    """Look up this instance's existing document with the same filename, if
    any — used to supersede the old version on re-upload rather than
    leaving both versions' chunks coexisting in the vector store."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM agent_instance_documents "
                "WHERE instance_id = %s AND filename = %s;",
                (instance_id, filename),
            )
            return cur.fetchone()


def list_documents(instance_id: int) -> list[dict]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM agent_instance_documents "
                "WHERE instance_id = %s ORDER BY created_at;",
                (instance_id,),
            )
            return cur.fetchall()


def get_document(document_id: int) -> dict | None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM agent_instance_documents WHERE id = %s;",
                (document_id,),
            )
            return cur.fetchone()


def delete_document(document_id: int) -> dict | None:
    """Deletes and returns the row (including chunk_ids) so the caller can
    also remove the corresponding vectors from Chroma."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM agent_instance_documents WHERE id = %s RETURNING *;",
                (document_id,),
            )
            row = cur.fetchone()
        conn.commit()
    return row
