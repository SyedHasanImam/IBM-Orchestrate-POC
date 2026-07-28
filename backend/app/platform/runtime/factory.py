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
from app.platform.schema.workflow_config import (
    ApprovalGateNodeConfig,
    FinalizeNodeConfig,
    LlmAgentNodeConfig,
    WorkflowConfig,
)
from app.platform.tools.registry import TOOL_REGISTRY


def _invoke_config(run_name: str) -> dict:
    return {"run_name": run_name, "callbacks": [get_langfuse_handler()]}


def build_agent_from_config(node: LlmAgentNodeConfig, name: str | None = None):
    """Build a standalone LangChain agent from an LlmAgentNodeConfig. Used
    both to build a pipeline node (below) and, unwrapped, as a supervisor
    collaborator (Phase 11) — one place that turns a node config into a
    real agent, reused for both purposes.

    `node.model` is a Settings attribute name (e.g. "aggregation_model"),
    not a literal model id — this keeps model-tier swapping an env-var
    change (backend/.env) rather than a YAML edit.
    """
    model_name = getattr(settings, node.model)
    tools = [TOOL_REGISTRY[tool_name] for tool_name in node.tools]
    model = init_chat_model(
        model_name, timeout=LLM_TIMEOUT_SECONDS, max_retries=LLM_MAX_RETRIES
    )
    return create_agent(
        model,
        tools=tools or None,
        system_prompt=node.system_prompt,
        checkpointer=None,
        name=name,
    )


def _build_llm_agent_node(workflow_name: str, node: LlmAgentNodeConfig):
    def node_fn(state: dict) -> dict:
        agent = build_agent_from_config(node)
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
