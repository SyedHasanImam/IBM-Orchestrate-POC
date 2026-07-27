import psycopg
from langchain_core.messages import HumanMessage

from app.agents.trustee_compliance_reporting.data_aggregation import (
    build_data_aggregation_agent,
)
from app.core.config import settings
from app.core.observability import flush_langfuse, get_langfuse_handler
from app.platform.audit.schema import ensure_schema
from app.platform.runtime.checkpointer import postgres_checkpointer
from conftest import extract_text


def test_postgres_checkpointer_persists_across_independent_graph_instances():
    """Simulates a process restart: two entirely separate connections/graph
    instances, same thread_id, must share state via Neon (not just
    in-process memory, which is all MemorySaver could ever prove). Each
    connection is opened and closed explicitly, in its own `with` block, so
    this test never leaks a connection either."""
    thread_id = "phase3-test-postgres-persistence"
    config = {"configurable": {"thread_id": thread_id}}

    with postgres_checkpointer() as checkpointer_a:
        graph_a = build_data_aggregation_agent(checkpointer_a)
        graph_a.invoke(
            {
                "messages": [
                    HumanMessage(content="How many holding positions does the fund have?")
                ]
            },
            config=config,
        )

    with postgres_checkpointer() as checkpointer_b:
        graph_b = build_data_aggregation_agent(checkpointer_b)
        followup = graph_b.invoke(
            {"messages": [HumanMessage(content="What number did you just tell me?")]},
            config=config,
        )

    final_text = extract_text(followup["messages"][-1])
    assert "22" in final_text


def test_agent_invocation_traces_to_langfuse_without_error(checkpointer):
    graph = build_data_aggregation_agent(checkpointer)
    handler = get_langfuse_handler()
    config = {
        "configurable": {"thread_id": "phase3-test-langfuse"},
        "callbacks": [handler],
    }

    result = graph.invoke(
        {
            "messages": [
                HumanMessage(content="How many holding positions does the fund have?")
            ]
        },
        config=config,
    )
    flush_langfuse()

    assert "22" in extract_text(result["messages"][-1])


def test_agent_registry_and_audit_log_tables_exist():
    """agent_registry stays empty until Phase 8 populates it from YAML.
    audit_log is NOT asserted empty here — Phase 6 onward deliberately
    writes real approval/rejection rows to it, so "empty" is only ever a
    transient truth, not a structural guarantee. This test just confirms
    both tables exist and are queryable."""
    ensure_schema()

    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('agent_registry', 'audit_log');
                """
            )
            tables = {row[0] for row in cur.fetchall()}
            assert tables == {"agent_registry", "audit_log"}

            cur.execute("SELECT count(*) FROM agent_registry;")
            assert cur.fetchone()[0] == 0

            cur.execute("SELECT count(*) FROM audit_log;")
            assert cur.fetchone()[0] >= 0
