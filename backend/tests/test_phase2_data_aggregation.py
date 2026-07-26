from langchain_core.messages import HumanMessage

from app.agents.trustee_compliance_reporting.data_aggregation import (
    build_data_aggregation_agent,
)
from app.platform.tools.fund_holdings import get_fund_holdings
from conftest import extract_text


def test_get_fund_holdings_returns_all_22_rows():
    holdings = get_fund_holdings.invoke({})
    assert len(holdings) == 22
    security_ids = {h["security_id"] for h in holdings}
    assert "PK0080101018" in security_ids  # OGDC
    assert "CASH-001" in security_ids


def test_agent_summarizes_holdings_correctly(checkpointer):
    graph = build_data_aggregation_agent(checkpointer)
    config = {"configurable": {"thread_id": "phase2-test-summary"}}

    result = graph.invoke(
        {
            "messages": [
                HumanMessage(
                    content=(
                        "How many holding positions does the fund currently "
                        "have, and what is the largest single equity "
                        "position by weight?"
                    )
                )
            ]
        },
        config=config,
    )

    final_text = extract_text(result["messages"][-1])
    assert "22" in final_text
    assert "OGDC" in final_text or "Oil & Gas Development" in final_text


def test_thread_state_persists_across_invocations(checkpointer):
    graph = build_data_aggregation_agent(checkpointer)
    config = {"configurable": {"thread_id": "phase2-test-memory"}}

    graph.invoke(
        {
            "messages": [
                HumanMessage(content="How many holding positions does the fund have?")
            ]
        },
        config=config,
    )
    followup = graph.invoke(
        {"messages": [HumanMessage(content="What number did you just tell me?")]},
        config=config,
    )

    final_text = extract_text(followup["messages"][-1])
    assert "22" in final_text
