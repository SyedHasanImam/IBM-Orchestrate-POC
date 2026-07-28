from langchain.chat_models import init_chat_model
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph_supervisor import create_supervisor
from langgraph_supervisor.handoff import (
    METADATA_KEY_HANDOFF_DESTINATION,
    METADATA_KEY_IS_HANDOFF_BACK,
)

from app.agents.trustee_compliance_reporting import (
    WORKFLOW_YAML_PATH as TRUSTEE_COMPLIANCE_WORKFLOW_YAML_PATH,
)
from app.core.config import LLM_MAX_RETRIES, LLM_TIMEOUT_SECONDS, settings
from app.core.messages import extract_text
from app.platform.runtime.factory import build_agent_from_config
from app.platform.runtime.loader import load_workflow_config

COLLABORATOR_NAMES = {"holdings_agent", "compliance_agent"}

SUPERVISOR_PROMPT = (
    "You are the routing supervisor for a mutual fund's agent platform. "
    "Route each question to exactly one specialist and let them answer — "
    "do not try to answer compliance or holdings questions yourself:\n"
    "- holdings_agent: questions about the fund's current portfolio "
    "holdings (positions, quantities, weights).\n"
    "- compliance_agent: questions about regulatory/mandate compliance, "
    "exposure limits, or breach status.\n"
    "Never attempt to generate a full trustee compliance report yourself — "
    "that only runs through its dedicated workflow, not this chat."
)


def _collaborator(yaml_path, node_name: str, agent_name: str):
    config = load_workflow_config(yaml_path)
    node = next(n for n in config.nodes if n.name == node_name)
    return build_agent_from_config(node, name=agent_name)


def build_chat_supervisor(checkpointer: BaseCheckpointSaver):
    """Ad hoc Q&A entry point, separate from the fixed report-generation
    pipelines. Reuses the exact same node configs already defined in the
    two workflow YAMLs as standalone collaborators — no new prompts."""
    collaborators = [
        _collaborator(
            TRUSTEE_COMPLIANCE_WORKFLOW_YAML_PATH, "aggregation", "holdings_agent"
        ),
        _collaborator(
            TRUSTEE_COMPLIANCE_WORKFLOW_YAML_PATH,
            "compliance_check",
            "compliance_agent",
        ),
    ]

    model = init_chat_model(
        settings.aggregation_model,
        timeout=LLM_TIMEOUT_SECONDS,
        max_retries=LLM_MAX_RETRIES,
    )

    supervisor = create_supervisor(
        collaborators,
        model=model,
        prompt=SUPERVISOR_PROMPT,
    )
    return supervisor.compile(checkpointer=checkpointer)


def extract_routed_to(messages: list) -> str | None:
    """Read which collaborator most recently handled the conversation, off
    the handoff ToolMessage langgraph-supervisor tags automatically —
    rather than guessing from the answer text."""
    for message in reversed(messages):
        destination = getattr(message, "response_metadata", {}).get(
            METADATA_KEY_HANDOFF_DESTINATION
        )
        if destination:
            return destination
    return None


def extract_final_answer(messages: list) -> str:
    """Return the collaborator's actual answer, not whatever the supervisor
    says afterward once it regains control — after a handoff, the
    supervisor takes another turn and often adds its own short (and often
    vague) wrap-up rather than repeating the collaborator's real answer, so
    the true last message in `messages` isn't reliably "the answer"."""
    for message in reversed(messages):
        if getattr(message, "response_metadata", {}).get(
            METADATA_KEY_IS_HANDOFF_BACK
        ):
            continue
        if getattr(message, "name", None) in COLLABORATOR_NAMES:
            return extract_text(message)
    return extract_text(messages[-1])
