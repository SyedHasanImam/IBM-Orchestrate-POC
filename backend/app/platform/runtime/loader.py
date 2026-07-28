import json
from pathlib import Path

import psycopg
import yaml
from psycopg.rows import dict_row

from app.core.config import DB_CONNECT_TIMEOUT_SECONDS, settings
from app.platform.schema.workflow_config import WorkflowConfig


def load_workflow_config(yaml_path: Path) -> WorkflowConfig:
    with open(yaml_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return WorkflowConfig.model_validate(raw)


def register_workflow(config: WorkflowConfig) -> None:
    """Upsert this workflow's config into the agent registry — this is what
    makes the catalog table reflect what's actually deployed, driven by the
    YAML rather than a manual DB edit."""
    with psycopg.connect(
        settings.database_url, connect_timeout=DB_CONNECT_TIMEOUT_SECONDS
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent_registry (name, description, version, config)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET
                    description = EXCLUDED.description,
                    version = EXCLUDED.version,
                    config = EXCLUDED.config,
                    updated_at = now();
                """,
                (
                    config.name,
                    config.description,
                    config.version,
                    json.dumps(config.model_dump()),
                ),
            )
        conn.commit()


def list_registered_workflows() -> list[dict]:
    """Read the agent catalog straight from Postgres — the UI's catalog
    view reflects what's actually registered, not a hardcoded list."""
    with psycopg.connect(
        settings.database_url,
        connect_timeout=DB_CONNECT_TIMEOUT_SECONDS,
        row_factory=dict_row,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, description, version, updated_at "
                "FROM agent_registry ORDER BY name;"
            )
            return cur.fetchall()
