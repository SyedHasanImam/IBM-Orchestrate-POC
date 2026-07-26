from contextlib import contextmanager

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row

from app.core.config import settings


@contextmanager
def postgres_checkpointer():
    """Open a single Postgres connection for a LangGraph checkpointer and
    guarantee it gets closed, instead of leaking one connection per agent
    build. A real connection pool (for a long-running server process) is
    deferred to Phase 7, when there's an actual app lifecycle to hook it
    into — this just stops today's short-lived callers (tests, scripts)
    from leaking connections against Neon."""
    conn = psycopg.connect(
        settings.database_url,
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
    )
    try:
        checkpointer = PostgresSaver(conn)
        checkpointer.setup()
        yield checkpointer
    finally:
        conn.close()
