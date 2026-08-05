from typing import Any, TypedDict

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.core.config import LLM_MAX_RETRIES, LLM_TIMEOUT_SECONDS, settings
from app.core.messages import extract_text
from app.core.observability import get_langfuse_handler
from app.platform.audit.log import record_report_decision
from app.platform.instances.store import get_instance
from app.platform.rag.retrieval import make_search_compliance_kb_tool
from app.platform.schema.workflow_config import (
    ApprovalGateNodeConfig,
    FinalizeNodeConfig,
    LlmAgentNodeConfig,
    WorkflowConfig,
)
from app.platform.tools.compliance_rules import make_check_compliance_limits_tool
from app.platform.tools.exposure_summary import make_get_portfolio_exposure_summary_tool
from app.platform.tools.fund_holdings import make_get_fund_holdings_tool
from app.platform.tools.reconciliation import (
    make_get_corporate_actions_tool,
    make_get_custodian_statement_tool,
    make_get_fund_ledger_tool,
    make_get_trade_blotter_tool,
    make_match_positions_tool,
)
from app.platform.tools.registry import TOOL_REGISTRY

INSTANCE_SCOPED_TOOL_FACTORIES = {
    "search_compliance_kb": make_search_compliance_kb_tool,
    "get_fund_holdings": make_get_fund_holdings_tool,
    "get_portfolio_exposure_summary": make_get_portfolio_exposure_summary_tool,
    "check_compliance_limits": make_check_compliance_limits_tool,
    "get_fund_ledger": make_get_fund_ledger_tool,
    "get_custodian_statement": make_get_custodian_statement_tool,
    "get_trade_blotter": make_get_trade_blotter_tool,
    "get_corporate_actions": make_get_corporate_actions_tool,
    "match_positions": make_match_positions_tool,
}


def _invoke_config(run_name: str) -> dict:
    return {"run_name": run_name, "callbacks": [get_langfuse_handler()]}


def llm_model_kwargs(llm_config: dict | None) -> dict:
    """Turn an instance's optional llm_config (temperature/max_tokens
    overrides, the Behavior tab's "Model settings") into init_chat_model
    kwargs — only the keys actually set, so an agent with no overrides
    keeps using its template's plain model exactly as before. Shared by
    both this module's pipeline-node agents and agent_chat.py's per-
    instance chat agent, so an override applies consistently everywhere
    that agent answers from."""
    if not llm_config:
        return {}
    kwargs = {}
    if llm_config.get("temperature") is not None:
        kwargs["temperature"] = llm_config["temperature"]
    if llm_config.get("max_tokens") is not None:
        kwargs["max_tokens"] = llm_config["max_tokens"]
    return kwargs


def resolve_tool(tool_name: str, instance_id: int | None):
    """Several tools need to operate on one specific agent instance's own
    data — its Knowledge documents, its uploaded holdings/reconciliation
    data — rather than a shared global default. When we know which instance
    this run belongs to, bind the tool to that instance instead of the
    TOOL_REGISTRY's shared fallback. Falls back to the shared default when
    there's no instance context (e.g. the chat supervisor's collaborators,
    which aren't scoped to one instance). Also used directly by
    agent_chat.py to resolve a per-instance chat's own tool list."""
    factory = INSTANCE_SCOPED_TOOL_FACTORIES.get(tool_name)
    if factory is not None and instance_id is not None:
        return factory(instance_id)
    return TOOL_REGISTRY[tool_name]


def build_agent_from_config(
    node: LlmAgentNodeConfig, name: str | None = None, instance_id: int | None = None
):
    """Build a standalone LangChain agent from an LlmAgentNodeConfig. Used
    both to build a pipeline node (below) and, unwrapped, as a supervisor
    collaborator (Phase 11) — one place that turns a node config into a
    real agent, reused for both purposes.

    `node.model` is a Settings attribute name (e.g. "aggregation_model"),
    not a literal model id — this keeps model-tier swapping an env-var
    change (backend/.env) rather than a YAML edit.
    """
    model_name = getattr(settings, node.model)
    tools = [resolve_tool(tool_name, instance_id) for tool_name in node.tools]
    instance = get_instance(instance_id) if instance_id is not None else None
    model = init_chat_model(
        model_name,
        timeout=LLM_TIMEOUT_SECONDS,
        max_retries=LLM_MAX_RETRIES,
        **llm_model_kwargs(instance.get("llm_config") if instance else None),
    )
    return create_agent(
        model,
        tools=tools or None,
        system_prompt=node.system_prompt,
        checkpointer=None,
        name=name,
    )


def _build_llm_agent_node(workflow_name: str, node: LlmAgentNodeConfig):
    def node_fn(state: dict, config: RunnableConfig) -> dict:
        instance_id = config["configurable"].get("agent_instance_id")
        agent = build_agent_from_config(node, instance_id=instance_id)
        content = node.message_template.format(**state)
        result = agent.invoke(
            {"messages": [HumanMessage(content=content)]},
            config=_invoke_config(f"{workflow_name}-{node.name}"),
        )
        return {node.output_key: extract_text(result["messages"][-1])}

    return node_fn


def _build_approval_gate_node(node: ApprovalGateNodeConfig):
    def node_fn(state: dict) -> dict:
        decision = interrupt({"report": state[node.report_key], "message": node.message})
        return {"approval_decision": decision}

    return node_fn


def _build_finalize_node(workflow_name: str, node: FinalizeNodeConfig):
    def node_fn(state: dict, config: RunnableConfig) -> dict:
        decision = state["approval_decision"]
        thread_id = config["configurable"]["thread_id"]
        audit_log_id = record_report_decision(
            thread_id=thread_id,
            agent_name=workflow_name,
            decision=decision["decision"],
            actor=decision["actor"],
            report_text=state[node.report_key],
            comment=decision.get("comment"),
        )
        return {"audit_log_id": audit_log_id}

    return node_fn


def build_workflow_from_config(config: WorkflowConfig, checkpointer: BaseCheckpointSaver):
    """Build a compiled, fixed-edge LangGraph pipeline from a validated
    WorkflowConfig. Nodes execute in config.nodes order — no conditional
    routing, matching the audit-critical design these workflows need."""
    state_schema = TypedDict(
        f"{config.name}_state", {key: Any for key in config.state_keys}, total=False
    )
    graph = StateGraph(state_schema)

    for node in config.nodes:
        if isinstance(node, LlmAgentNodeConfig):
            graph.add_node(node.name, _build_llm_agent_node(config.name, node))
        elif isinstance(node, ApprovalGateNodeConfig):
            graph.add_node(node.name, _build_approval_gate_node(node))
        elif isinstance(node, FinalizeNodeConfig):
            graph.add_node(node.name, _build_finalize_node(config.name, node))

    node_names = [node.name for node in config.nodes]
    graph.add_edge(START, node_names[0])
    for current_name, next_name in zip(node_names, node_names[1:]):
        graph.add_edge(current_name, next_name)
    graph.add_edge(node_names[-1], END)

    return graph.compile(checkpointer=checkpointer)
