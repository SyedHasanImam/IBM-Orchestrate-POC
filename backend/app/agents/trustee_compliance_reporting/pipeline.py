import json
from typing import TypedDict

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from app.agents.trustee_compliance_reporting.compliance_checking import (
    build_compliance_agent,
)
from app.agents.trustee_compliance_reporting.data_aggregation import (
    build_data_aggregation_agent,
)
from app.agents.trustee_compliance_reporting.exposure_analysis import (
    compute_exposure_summary,
)
from app.agents.trustee_compliance_reporting.reporting import build_reporting_agent
from app.core.messages import extract_text
from app.core.observability import get_langfuse_handler
from app.platform.tools.fund_holdings import get_fund_holdings


class ComplianceReportState(TypedDict, total=False):
    holdings: list[dict]
    exposure_summary: dict
    compliance_findings: str
    report: str


def _invoke_config(run_name: str) -> dict:
    return {
        "run_name": run_name,
        "callbacks": [get_langfuse_handler()],
    }


def aggregation_node(state: ComplianceReportState) -> dict:
    agent = build_data_aggregation_agent(checkpointer=None)
    agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content="Retrieve and summarize the fund's current holdings."
                )
            ]
        },
        config=_invoke_config("compliance-report-aggregation"),
    )
    holdings = get_fund_holdings.invoke({})
    return {"holdings": holdings}


def compliance_check_node(state: ComplianceReportState) -> dict:
    exposure_summary = compute_exposure_summary(state["holdings"])
    agent = build_compliance_agent(checkpointer=None)
    result = agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content=(
                        "Here are the fund's computed portfolio exposures as "
                        f"JSON:\n\n{json.dumps(exposure_summary, indent=2)}\n\n"
                        "Check these against the mandate and SECP regulatory "
                        "limits."
                    )
                )
            ]
        },
        config=_invoke_config("compliance-report-compliance-check"),
    )
    findings = extract_text(result["messages"][-1])
    return {"exposure_summary": exposure_summary, "compliance_findings": findings}


def reporting_node(state: ComplianceReportState) -> dict:
    agent = build_reporting_agent(checkpointer=None)
    result = agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content=(
                        "Here are this month's compliance-checking findings:"
                        f"\n\n{state['compliance_findings']}"
                    )
                )
            ]
        },
        config=_invoke_config("compliance-report-reporting"),
    )
    report = extract_text(result["messages"][-1])
    return {"report": report}


def build_compliance_report_pipeline():
    """Fixed-edge pipeline: Aggregation -> Compliance Check -> Reporting.

    Deliberately hardcoded (no supervisor, no conditional routing, no
    checkpointer) — this is the audit-critical "generate the official
    report" path, where the step order must be provably fixed rather than
    LLM-decided. No HITL yet (Phase 6 adds the approval gate)."""
    graph = StateGraph(ComplianceReportState)
    graph.add_node("aggregation", aggregation_node)
    graph.add_node("compliance_check", compliance_check_node)
    graph.add_node("reporting", reporting_node)
    graph.add_edge(START, "aggregation")
    graph.add_edge("aggregation", "compliance_check")
    graph.add_edge("compliance_check", "reporting")
    graph.add_edge("reporting", END)
    return graph.compile()
