import json

import psycopg

from app.core.config import DB_CONNECT_TIMEOUT_SECONDS, settings


def record_report_decision(
    *,
    thread_id: str,
    agent_name: str,
    decision: str,
    actor: str,
    report_text: str,
    comment: str | None = None,
) -> int:
    """Write an immutable audit_log row for a human approval/rejection
    decision on a finalized report. Returns the new row's id."""
    event_type = "report_approved" if decision == "approved" else "report_rejected"
    payload = {"report": report_text, "comment": comment}

    with psycopg.connect(
        settings.database_url, connect_timeout=DB_CONNECT_TIMEOUT_SECONDS
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_log (thread_id, agent_name, event_type, actor, payload)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (thread_id, agent_name, event_type, actor, json.dumps(payload)),
            )
            row_id = cur.fetchone()[0]
        conn.commit()
    return row_id
