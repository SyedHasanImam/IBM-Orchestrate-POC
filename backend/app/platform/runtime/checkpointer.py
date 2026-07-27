from contextlib import contextmanager

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row

from app.core.config import DB_CONNECT_TIMEOUT_SECONDS, settings


@contextmanager
def postgres_checkpointer():
    """Open a single Postgres connection for a LangGraph checkpointer and
    guarantee it gets closed, instead of leaking one connection per agent
    build. A real connection pool (for a long-running server process) is
    used by the FastAPI app (Phase 7) — this helper is for short-lived
    callers (tests, scripts) that just need one connection, closed
    afterward, without leaking it."""
    conn = psycopg.connect(
        settings.database_url,
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
        connect_timeout=DB_CONNECT_TIMEOUT_SECONDS,
    )
    try:
        checkpointer = PostgresSaver(conn)
        checkpointer.setup()
        yield checkpointer
    finally:
        conn.close()
