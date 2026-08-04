from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.core.config import LLM_MAX_RETRIES, LLM_TIMEOUT_SECONDS, settings
from app.platform.runtime.factory import resolve_tool
from app.platform.runtime.report_tool import make_generate_report_tool, workflow_has_approval_gate
from app.platform.schema.workflow_config import WorkflowConfig

DEFAULT_SYSTEM_PROMPT_TEMPLATE = (
    "You are {display_name}, an agent on a fund management platform. "
    "{description}\n\n"
    "Use your available tools to answer questions using this agent's own "
    "attached data sources and Knowledge. If the answer isn't available "
    "through any of them, say so honestly rather than guessing."
)


def build_instance_agent(
    instance: dict,
    workflow_config: WorkflowConfig,
    *,
    name: str | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    include_report_tool: bool = False,
):
    """Build a plain LangChain agent scoped to one agent instance's own
    data — its tool list is derived from its own template's workflow config
    (the union of tools its pipeline stages use), so this works for any
    template rather than being hardcoded to one workflow's tools. Shared by
    both the per-agent chat (below) and the homepage chat supervisor's
    dynamic collaborators, so there's exactly one place that turns an
    instance into a real agent.

    include_report_tool is off by default and only turned on for the
    standalone per-agent chat — the homepage supervisor's collaborators
    don't get it. A resumed approval reliably reaches the paused pipeline
    when the collaborator IS the top-level invoked graph (one level of
    nesting), but not when it's a subgraph node inside the supervisor's own
    graph (two levels of nesting) — verified live: the resume call returns
    a normal-looking success message without ever actually finishing the
    pipeline or writing an audit log row. Silently "succeeding" without
    recording a decision is worse than not offering report generation
    there at all, so it stays off until that's properly understood."""
    system_prompt = DEFAULT_SYSTEM_PROMPT_TEMPLATE.format(
        display_name=instance["display_name"],
        description=instance["description"] or "No description provided.",
    )
    # Instructions (the Behavior tab) is layered on top of the identity
    # block rather than replacing it — mirrors watsonx Orchestrate, where
    # Description and Instructions are separate, both-always-present layers,
    # not one overriding the other.
    instructions = instance.get("instructions")
    if instructions:
        system_prompt = f"{system_prompt}\n\n{instructions}"
    model = init_chat_model(
        settings.compliance_model, timeout=LLM_TIMEOUT_SECONDS, max_retries=LLM_MAX_RETRIES
    )
    # Union with the user-added extras (the Toolset tab's "Add tool") — the
    # template's own tools are the fixed base set; extra_tools lets the user
    # extend a specific instance's toolset beyond what its template alone
    # would give it.
    tool_names = {
        tool_name
        for node in workflow_config.nodes
        if node.type == "llm_agent"
        for tool_name in node.tools
    } | set(instance.get("extra_tools") or [])
    tools = [resolve_tool(tool_name, instance["id"]) for tool_name in sorted(tool_names)]
    if include_report_tool and checkpointer is not None and workflow_has_approval_gate(
        workflow_config
    ):
        tools.append(make_generate_report_tool(instance, workflow_config, checkpointer))
    return create_agent(
        model,
        tools=tools or None,
        system_prompt=system_prompt,
        checkpointer=checkpointer,
        name=name,
    )


def build_agent_preview_chat(
    instance: dict, workflow_config: WorkflowConfig, checkpointer: BaseCheckpointSaver
):
    """A standalone chat agent for one specific agent instance — lets you
    ask it anything using its own attached Knowledge and data, whether it's
    still a draft (the editor's Preview panel) or already deployed (its own
    page). Distinct from the multi-agent chat supervisor: there's no
    routing here, just this one agent answering with its own data."""
    return build_instance_agent(
        instance, workflow_config, checkpointer=checkpointer, include_report_tool=True
    )
