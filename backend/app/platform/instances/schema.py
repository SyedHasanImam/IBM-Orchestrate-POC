import psycopg

from app.core.config import DB_CONNECT_TIMEOUT_SECONDS, settings

AGENT_INSTANCES_DDL = """
CREATE TABLE IF NOT EXISTS agent_instances (
    id SERIAL PRIMARY KEY,
    template_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    instructions TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

# Older databases created this column back when it was an all-or-nothing
# system prompt replacement named system_prompt_override; it's now composed
# additively with the auto-generated identity/description block, so it was
# renamed to instructions to match. Guarded so it only runs once.
AGENT_INSTANCES_RENAME_INSTRUCTIONS_DDL = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'agent_instances' AND column_name = 'system_prompt_override'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'agent_instances' AND column_name = 'instructions'
    ) THEN
        ALTER TABLE agent_instances RENAME COLUMN system_prompt_override TO instructions;
    END IF;
END $$;
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

# Optional — the date this document's content is effective as of (e.g. a
# mandate revision date), as distinct from created_at (when it happened to
# be uploaded to this platform). Without this, a stale regulatory clause
# looks identical to a current one to both the retrieval tool and whoever
# reads its citation.
AGENT_INSTANCE_DOCUMENTS_EFFECTIVE_DATE_DDL = """
ALTER TABLE agent_instance_documents
    ADD COLUMN IF NOT EXISTS effective_date DATE;
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

# Tool names the user has manually added on top of whatever the template's
# own workflow already gives this agent (the Toolset tab's "Add tool") — a
# plain array of TOOL_REGISTRY keys, validated at the API layer.
AGENT_INSTANCES_EXTRA_TOOLS_COLUMN_DDL = """
ALTER TABLE agent_instances
    ADD COLUMN IF NOT EXISTS extra_tools TEXT[] NOT NULL DEFAULT '{}';
"""

# Optional per-agent temperature/max_tokens overrides (the Behavior tab's
# "Model settings") — a real IBM Orchestrate concept, empty by default so
# every existing agent keeps using the template's plain model with no
# override at all.
AGENT_INSTANCES_LLM_CONFIG_COLUMN_DDL = """
ALTER TABLE agent_instances
    ADD COLUMN IF NOT EXISTS llm_config JSONB NOT NULL DEFAULT '{}'::jsonb;
"""

# Other deployed instances this agent can hand a question off to as a fixed,
# build-time roster (the Toolset tab's "Add agent") — distinct from the
# homepage chat's "Manage agents" picker, which is a runtime, per-session
# choice. Empty by default so an agent behaves exactly as before until
# collaborators are actually added.
AGENT_INSTANCES_COLLABORATOR_IDS_COLUMN_DDL = """
ALTER TABLE agent_instances
    ADD COLUMN IF NOT EXISTS collaborator_ids INTEGER[] NOT NULL DEFAULT '{}';
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
            cur.execute(AGENT_INSTANCES_RENAME_INSTRUCTIONS_DDL)
            cur.execute(AGENT_INSTANCE_DOCUMENTS_DDL)
            cur.execute(AGENT_INSTANCE_DOCUMENTS_EFFECTIVE_DATE_DDL)
            cur.execute(AGENT_INSTANCES_HOLDINGS_COLUMNS_DDL)
            cur.execute(AGENT_INSTANCES_RECONCILIATION_COLUMN_DDL)
            cur.execute(AGENT_INSTANCES_CHAT_COLUMN_DDL)
            cur.execute(AGENT_INSTANCES_EXTRA_TOOLS_COLUMN_DDL)
            cur.execute(AGENT_INSTANCES_LLM_CONFIG_COLUMN_DDL)
            cur.execute(AGENT_INSTANCES_COLLABORATOR_IDS_COLUMN_DDL)
        conn.commit()
