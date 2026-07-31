import psycopg

from app.core.config import DB_CONNECT_TIMEOUT_SECONDS, settings

AGENT_INSTANCES_DDL = """
CREATE TABLE IF NOT EXISTS agent_instances (
    id SERIAL PRIMARY KEY,
    template_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    system_prompt_override TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

AGENT_INSTANCE_DOCUMENTS_DDL = """
CREATE TABLE IF NOT EXISTS agent_instance_documents (
    id SERIAL PRIMARY KEY,
    instance_id INTEGER NOT NULL REFERENCES agent_instances(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    chunk_count INTEGER NOT NULL,
    chunk_ids TEXT[] NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

# A holdings snapshot is attached to the agent itself (like Knowledge), not
# per report run — one snapshot per instance, replaced on re-upload rather
# than accumulated like documents.
AGENT_INSTANCES_HOLDINGS_COLUMNS_DDL = """
ALTER TABLE agent_instances
    ADD COLUMN IF NOT EXISTS holdings_snapshot JSONB,
    ADD COLUMN IF NOT EXISTS holdings_warnings JSONB,
    ADD COLUMN IF NOT EXISTS holdings_filename TEXT,
    ADD COLUMN IF NOT EXISTS holdings_uploaded_at TIMESTAMPTZ;
"""

# Reconciliation needs several independent data slots (ledger, custodian
# statement, trade blotter, corporate actions) rather than the single
# holdings snapshot compliance uses — one JSONB column keyed by doc type
# keeps that generic instead of adding four more columns per document.
AGENT_INSTANCES_RECONCILIATION_COLUMN_DDL = """
ALTER TABLE agent_instances
    ADD COLUMN IF NOT EXISTS reconciliation_inputs JSONB NOT NULL DEFAULT '{}'::jsonb;
"""

# Whether this deployed instance is currently one of the collaborators the
# homepage chat's routing supervisor can hand questions off to — toggled by
# the user from the chat's "Manage agents" picker, not tied to deployment
# itself (a deployed agent can still be left out of the chat).
AGENT_INSTANCES_CHAT_COLUMN_DDL = """
ALTER TABLE agent_instances
    ADD COLUMN IF NOT EXISTS included_in_chat BOOLEAN NOT NULL DEFAULT false;
"""


def ensure_instances_schema() -> None:
    """Create the agent_instances/agent_instance_documents tables (and add
    the holdings-snapshot, reconciliation-inputs, and chat-inclusion
    columns) if they don't already exist yet. Idempotent — safe to call on
    every startup."""
    with psycopg.connect(
        settings.database_url, connect_timeout=DB_CONNECT_TIMEOUT_SECONDS
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(AGENT_INSTANCES_DDL)
            cur.execute(AGENT_INSTANCE_DOCUMENTS_DDL)
            cur.execute(AGENT_INSTANCES_HOLDINGS_COLUMNS_DDL)
            cur.execute(AGENT_INSTANCES_RECONCILIATION_COLUMN_DDL)
            cur.execute(AGENT_INSTANCES_CHAT_COLUMN_DDL)
        conn.commit()
