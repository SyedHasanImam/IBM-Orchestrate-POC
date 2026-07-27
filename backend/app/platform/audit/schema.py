import psycopg

from app.core.config import DB_CONNECT_TIMEOUT_SECONDS, settings

AGENT_REGISTRY_DDL = """
CREATE TABLE IF NOT EXISTS agent_registry (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    version TEXT NOT NULL DEFAULT '0.1.0',
    config JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

AUDIT_LOG_DDL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    thread_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    tool_name TEXT,
    actor TEXT,
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def ensure_schema() -> None:
    """Create the core platform tables (agent registry, audit log) if they
    don't already exist yet. Idempotent — safe to call on every startup."""
    with psycopg.connect(
        settings.database_url, connect_timeout=DB_CONNECT_TIMEOUT_SECONDS
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(AGENT_REGISTRY_DDL)
            cur.execute(AUDIT_LOG_DDL)
        conn.commit()
