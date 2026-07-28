import uuid

import pytest
from langchain_core.messages import HumanMessage

from app.platform.rag.ingest import ingest_compliance_documents
from app.platform.runtime.checkpointer import postgres_checkpointer
from app.platform.runtime.supervisor import (
    build_chat_supervisor,
    extract_final_answer,
    extract_routed_to,
)


@pytest.fixture(scope="module", autouse=True)
def ingested_kb():
    ingest_compliance_documents()
    yield


QUESTIONS = [
    (
        "holdings-1",
        "How many holding positions does the fund currently have?",
        "holdings_agent",
        ["22"],
    ),
    (
        "holdings-2",
        "What is the fund's largest single equity holding by weight?",
        "holdings_agent",
        ["OGDC", "Oil & Gas Development"],
    ),
    (
        "compliance-1",
        "Is the fund in breach of the single-issuer exposure limit? What clause covers it?",
        "compliance_agent",
        ["6.1"],
    ),
    (
        "compliance-2",
        "What is the fund's minimum liquidity requirement?",
        "compliance_agent",
        ["7.1"],
    ),
]


@pytest.mark.parametrize("label,question,expected_agent,expected_terms", QUESTIONS)
def test_question_routes_to_correct_collaborator(
    label, question, expected_agent, expected_terms
):
    # A fresh thread_id per run — reusing one across repeated test runs would
    # accumulate conversation history in the real Postgres checkpointer and
    # shift the model's behavior turn over turn.
    thread_id = f"phase11-{label}-{uuid.uuid4()}"
    with postgres_checkpointer() as checkpointer:
        supervisor = build_chat_supervisor(checkpointer)
        result = supervisor.invoke(
            {"messages": [HumanMessage(content=question)]},
            config={"configurable": {"thread_id": thread_id}},
        )

    assert extract_routed_to(result["messages"]) == expected_agent

    answer = extract_final_answer(result["messages"]).lower()
    assert any(term.lower() in answer for term in expected_terms)


def test_supervisor_never_generates_a_full_report():
    with postgres_checkpointer() as checkpointer:
        supervisor = build_chat_supervisor(checkpointer)
        result = supervisor.invoke(
            {
                "messages": [
                    HumanMessage(
                        content="How many holding positions does the fund have?"
                    )
                ]
            },
            config={"configurable": {"thread_id": f"phase11-no-report-{uuid.uuid4()}"}},
        )

    answer = extract_final_answer(result["messages"]).lower()
    # These only ever appear in the Reporting Agent's formatted output —
    # their absence confirms the chat path never touches report generation.
    assert "executive summary" not in answer
    assert "pending trustee review" not in answer
