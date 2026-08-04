from langchain_core.tools import tool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command, interrupt

from app.platform.runtime.factory import build_workflow_from_config
from app.platform.schema.workflow_config import WorkflowConfig
from app.platform.tools.data_sources import DataSourceSpec, required_data_sources


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

    The pipeline keeps its own checkpointed sub-graph (built fresh here but
    resolved to the same thread every time via pipeline_thread_id), so
    calling this tool again after the human decision is submitted never
    re-runs the upstream LLM stages a second time — only the already-paused
    approval step resumes.
    """
    instance_id = instance["id"]
    pipeline = build_workflow_from_config(workflow_config, checkpointer)
    # One in-flight report per instance at a time, same as the old Run
    # Report button (a fresh run per click) — simplified here to one stable
    # id per instance since the report is now identified by its owning
    # agent rather than a separate run id.
    pipeline_config = {
        "configurable": {
            "thread_id": f"chat-report-{instance_id}",
            "agent_instance_id": instance_id,
        }
    }

    @tool
    def generate_report() -> str:
        """Generate this agent's official report by running its full data
        pipeline, then pause for a human's approve/reject decision before
        it's finalized. Call this when the user asks you to generate,
        produce, draft, or run this period's report — not for ad hoc
        questions about the underlying data, which your other tools already
        answer directly."""
        missing = _missing_data_message(instance, workflow_config, instance.get("extra_tools"))
        if missing:
            return f"Can't generate this report yet — {missing}. Ask the user to attach it first."

        result = pipeline.invoke({}, config=pipeline_config)
        if "__interrupt__" in result:
            payload = result["__interrupt__"][0].value
            decision = interrupt(payload)
            result = pipeline.invoke(Command(resume=decision), config=pipeline_config)
        decision_made = result["approval_decision"]["decision"]
        return (
            f"Report generated and {decision_made}. Audit log id: "
            f"{result['audit_log_id']}.\n\n{result['report']}"
        )

    return generate_report
