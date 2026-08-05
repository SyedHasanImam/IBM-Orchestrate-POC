from langchain_core.tools import tool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command

from app.platform.runtime.factory import build_workflow_from_config
from app.platform.schema.workflow_config import WorkflowConfig
from app.platform.tools.data_sources import DataSourceSpec, required_data_sources

GENERATE_REPORT_TOOL_NAME = "generate_report"


def _pipeline_config(instance_id: int) -> dict:
    # One in-flight report per instance at a time, identified by the agent's
    # own id rather than a chat thread — this is what lets approval work the
    # same way regardless of which chat (this agent's own, or the homepage's
    # multi-agent one) asked for the report, and survive that chat's own
    # conversation graph being rebuilt between requests.
    return {
        "configurable": {
            "thread_id": f"chat-report-{instance_id}",
            "agent_instance_id": instance_id,
        }
    }


def workflow_has_approval_gate(workflow_config: WorkflowConfig) -> bool:
    return any(node.type == "approval_gate" for node in workflow_config.nodes)


def workflow_tool_names(workflow_config: WorkflowConfig) -> set[str]:
    return {
        tool_name
        for node in workflow_config.nodes
        if node.type == "llm_agent"
        for tool_name in node.tools
    }


def _has_data(instance: dict, spec: DataSourceSpec) -> bool:
    if spec.kind == "holdings":
        return bool(instance.get("holdings_snapshot"))
    inputs = instance.get("reconciliation_inputs") or {}
    return bool((inputs.get(spec.key) or {}).get("rows"))


def _missing_data_message(
    instance: dict, workflow_config: WorkflowConfig, extra_tools: list[str] | None = None
) -> str | None:
    """What's missing before this instance can generate a report, in plain
    language — or None if it has everything it needs. Kept as a real check
    (not just relying on the LLM to notice empty tool results) so asking to
    generate a report on a freshly-created instance fails with a clear
    message instead of quietly producing a report over an empty dataset.
    Checks tools added via Add Tool too, not just the template's own, since
    those need their own uploaded data the same way."""
    tool_names = workflow_tool_names(workflow_config) | set(extra_tools or [])
    missing = [
        spec.key.replace("_", " ")
        for spec in required_data_sources(tool_names)
        if spec.required and not _has_data(instance, spec)
    ]
    if missing:
        return f"this agent's {' and '.join(missing)} haven't been uploaded yet (Knowledge tab)"

    return None


def make_generate_report_tool(
    instance: dict, workflow_config: WorkflowConfig, checkpointer: BaseCheckpointSaver
):
    """Wrap this instance's existing deterministic report pipeline
    (aggregation -> checks -> reporting -> approval -> finalize) as a single
    tool the chat agent can call, so "generate this period's report" is just
    one more thing this agent can do in conversation rather than a separate
    button/page.

    Deliberately does NOT pause this tool's own enclosing chat turn with
    `interrupt()` — pausing the pipeline itself is enough, and it's tracked
    on the pipeline's own thread (see _pipeline_config), independent of
    whichever chat asked for it. Trying to also freeze the *chat's* graph
    and resume it later is exactly what broke report approval when this
    agent is one of several collaborators in the homepage's multi-agent
    chat: resuming a multi-agent conversation replays it from the top,
    which doesn't reliably reach the same tool call again. Real watsonx
    Orchestrate avoids this the same way — a Flow waiting on a human runs as
    its own tracked instance, not as a frozen chat turn. See
    get_pending_report/submit_report_decision below for how the actual
    approve/reject step is handled, decoupled from any chat's own state.
    """
    instance_id = instance["id"]
    pipeline = build_workflow_from_config(workflow_config, checkpointer)

    @tool
    def generate_report() -> str:
        """Generate this agent's official report by running its full data
        pipeline. If the report needs a human's approve/reject decision, say
        so plainly and stop — you cannot approve or reject it yourself. Call
        this when the user asks you to generate, produce, draft, or run this
        period's report — not for ad hoc questions about the underlying
        data, which your other tools already answer directly."""
        missing = _missing_data_message(instance, workflow_config, instance.get("extra_tools"))
        if missing:
            return f"Can't generate this report yet — {missing}. Ask the user to attach it first."

        result = pipeline.invoke({}, config=_pipeline_config(instance_id))
        if "__interrupt__" in result:
            payload = result["__interrupt__"][0].value
            return (
                f"{payload['report']}\n\n{payload['message']} This report is "
                "pending a human's approve/reject decision — I can't finalize "
                "it myself, so ask the user to approve or reject it."
            )
        decision_made = result["approval_decision"]["decision"]
        return (
            f"Report generated and {decision_made}. Audit log id: "
            f"{result['audit_log_id']}.\n\n{result['report']}"
        )

    return generate_report


def get_pending_report(
    instance_id: int, workflow_config: WorkflowConfig, checkpointer: BaseCheckpointSaver
) -> dict | None:
    """Whether this instance currently has a report waiting on a human
    decision — read directly off the pipeline's own checkpointed state,
    without invoking anything. Independent of which chat (this agent's own,
    or the homepage's multi-agent one) triggered generate_report, so both
    can surface the same pending approval the same way."""
    pipeline = build_workflow_from_config(workflow_config, checkpointer)
    snapshot = pipeline.get_state(_pipeline_config(instance_id))
    for task in snapshot.tasks:
        for pending in task.interrupts:
            return {"report": pending.value["report"], "message": pending.value["message"]}
    return None


def submit_report_decision(
    instance_id: int,
    workflow_config: WorkflowConfig,
    checkpointer: BaseCheckpointSaver,
    *,
    decision: str,
    actor: str,
    comment: str | None,
) -> dict:
    """Resume this instance's report pipeline directly, by its own thread —
    this is the actual fix: approval no longer depends on resuming whatever
    chat conversation asked for the report, so it works the same from this
    agent's own chat or the homepage's multi-agent chat."""
    pipeline = build_workflow_from_config(workflow_config, checkpointer)
    result = pipeline.invoke(
        Command(resume={"decision": decision, "actor": actor, "comment": comment}),
        config=_pipeline_config(instance_id),
    )
    return {
        "report": result["report"],
        "decision": result["approval_decision"]["decision"],
        "audit_log_id": result["audit_log_id"],
    }
