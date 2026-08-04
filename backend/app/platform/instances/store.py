import json

import psycopg
from psycopg.rows import dict_row

from app.core.config import DB_CONNECT_TIMEOUT_SECONDS, settings


def _connect():
    return psycopg.connect(
        settings.database_url,
        connect_timeout=DB_CONNECT_TIMEOUT_SECONDS,
        row_factory=dict_row,
    )


def create_instance(*, template_name: str, display_name: str, description: str) -> dict:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent_instances (template_name, display_name, description)
                VALUES (%s, %s, %s)
                RETURNING *;
                """,
                (template_name, display_name, description),
            )
            row = cur.fetchone()
        conn.commit()
    return row


def list_instances() -> list[dict]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM agent_instances ORDER BY updated_at DESC;")
            return cur.fetchall()


def get_instance(instance_id: int) -> dict | None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM agent_instances WHERE id = %s;", (instance_id,))
            return cur.fetchone()


UPDATABLE_FIELDS = {
    "display_name",
    "description",
    "instructions",
    "included_in_chat",
    "extra_tools",
}


def update_instance(instance_id: int, **fields) -> dict | None:
    """Patch whichever of display_name/description/instructions/
    included_in_chat/extra_tools were actually provided. Returns None if the
    instance doesn't exist."""
    if not fields:
        return get_instance(instance_id)
    unknown = fields.keys() - UPDATABLE_FIELDS
    if unknown:
        raise ValueError(f"Cannot update fields: {sorted(unknown)}")

    set_clause = ", ".join(f"{key} = %s" for key in fields)
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE agent_instances
                SET {set_clause}, updated_at = now()
                WHERE id = %s
                RETURNING *;
                """,
                (*fields.values(), instance_id),
            )
            row = cur.fetchone()
        conn.commit()
    return row


def set_holdings(
    instance_id: int, *, holdings: list[dict], warnings: list[dict], filename: str
) -> dict | None:
    """Replace this instance's holdings snapshot — attached once, like
    Knowledge, and reused by every report run until it's replaced again."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE agent_instances
                SET holdings_snapshot = %s,
                    holdings_warnings = %s,
                    holdings_filename = %s,
                    holdings_uploaded_at = now(),
                    updated_at = now()
                WHERE id = %s
                RETURNING *;
                """,
                (json.dumps(holdings), json.dumps(warnings), filename, instance_id),
            )
            row = cur.fetchone()
        conn.commit()
    return row


RECONCILIATION_DOCUMENT_TYPES = (
    "ledger",
    "custodian_statement",
    "trade_blotter",
    "corporate_actions",
)


def set_reconciliation_input(
    instance_id: int, *, doc_type: str, rows: list[dict], warnings: list[dict], filename: str
) -> dict | None:
    """Replace one of this instance's reconciliation data slots (ledger,
    custodian_statement, trade_blotter, or corporate_actions) — each
    attached independently, like Knowledge, and reused by every
    reconciliation run until that slot is replaced again. jsonb_set only
    touches this one key, so uploading one document never clobbers the
    others already attached."""
    if doc_type not in RECONCILIATION_DOCUMENT_TYPES:
        raise ValueError(f"Unknown reconciliation document type: {doc_type}")
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE agent_instances
                SET reconciliation_inputs = jsonb_set(
                        reconciliation_inputs,
                        %s,
                        jsonb_build_object(
                            'rows', %s::jsonb,
                            'warnings', %s::jsonb,
                            'filename', %s::text,
                            'uploaded_at', now()
                        ),
                        true
                    ),
                    updated_at = now()
                WHERE id = %s
                RETURNING *;
                """,
                ([doc_type], json.dumps(rows), json.dumps(warnings), filename, instance_id),
            )
            row = cur.fetchone()
        conn.commit()
    return row


def delete_instance(instance_id: int) -> dict | None:
    """Delete this agent instance. Its documents row cascades automatically
    (ON DELETE CASCADE); the caller is still responsible for cleaning up its
    Chroma collection, which lives outside Postgres."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM agent_instances WHERE id = %s RETURNING *;",
                (instance_id,),
            )
            row = cur.fetchone()
        conn.commit()
    return row


def deploy_instance(instance_id: int) -> dict | None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE agent_instances
                SET status = 'deployed', updated_at = now()
                WHERE id = %s
                RETURNING *;
                """,
                (instance_id,),
            )
            row = cur.fetchone()
        conn.commit()
    return row
