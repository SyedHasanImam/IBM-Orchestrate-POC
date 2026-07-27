import json
from typing import TypedDict

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

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
from app.platform.audit.log import record_report_decision
from app.platform.tools.fund_holdings import get_fund_holdings

AGENT_NAME = "trustee_compliance_reporting"


class ComplianceReportState(TypedDict, total=False):
    holdings: list[dict]
    exposure_summary: dict
    compliance_findings: str
    report: str
    approval_decision: dict
    audit_log_id: int


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


def approval_gate_node(state: ComplianceReportState) -> dict:
    """Unconditionally pauses for human review — the LLM never decides
    whether to stop here, matching the audit-critical, fixed-edge design of
    this pipeline. Resumed via Command(resume=<decision dict>), where
    decision = {"decision": "approved" | "rejected", "actor": str,
    "comment": str | None}."""
    decision = interrupt(
        {
            "report": state["report"],
            "message": (
                "Please review and approve or reject this month's trustee "
                "compliance report."
            ),
        }
    )
    return {"approval_decision": decision}


def finalize_node(state: ComplianceReportState, config: RunnableConfig) -> dict:
    decision = state["approval_decision"]
    thread_id = config["configurable"]["thread_id"]
    audit_log_id = record_report_decision(
        thread_id=thread_id,
        agent_name=AGENT_NAME,
        decision=decision["decision"],
        actor=decision["actor"],
        report_text=state["report"],
        comment=decision.get("comment"),
    )
    return {"audit_log_id": audit_log_id}


def build_compliance_report_pipeline(checkpointer: BaseCheckpointSaver):
    """Fixed-edge pipeline: Aggregation -> Compliance Check -> Reporting ->
    Approval Gate -> Finalize.

    Deliberately hardcoded (no supervisor, no conditional routing) — this is
    the audit-critical "generate the official report" path, where the step
    order must be provably fixed rather than LLM-decided. A real
    checkpointer is now required: interrupt()/resume has nowhere to persist
    paused state without one."""
    graph = StateGraph(ComplianceReportState)
    graph.add_node("aggregation", aggregation_node)
    graph.add_node("compliance_check", compliance_check_node)
    graph.add_node("reporting", reporting_node)
    graph.add_node("approval_gate", approval_gate_node)
    graph.add_node("finalize", finalize_node)
    graph.add_edge(START, "aggregation")
    graph.add_edge("aggregation", "compliance_check")
    graph.add_edge("compliance_check", "reporting")
    graph.add_edge("reporting", "approval_gate")
    graph.add_edge("approval_gate", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer)
