import re

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph_supervisor import create_supervisor
from langgraph_supervisor.handoff import (
    METADATA_KEY_HANDOFF_DESTINATION,
    METADATA_KEY_IS_HANDOFF_BACK,
)

from app.core.config import LLM_MAX_RETRIES, LLM_TIMEOUT_SECONDS, settings
from app.core.messages import extract_text
from app.platform.runtime.agent_chat import build_instance_agent
from app.platform.schema.workflow_config import WorkflowConfig

# Shown when no agent has been added to the chat yet — a plain conversational
# agent rather than either blocking the chat outright or letting it invent
# answers about fund data it has no actual access to.
NO_AGENTS_SYSTEM_PROMPT = (
    "You are a general assistant on a fund management platform. No "
    "specialist agents have been added to this chat yet, so you don't have "
    "access to any of the platform's real fund data. If asked about "
    "specific holdings, compliance, or reconciliation status, say plainly "
    "that no agents are configured for this chat yet and suggest adding "
    "one from Discover, rather than guessing an answer."
)


def collaborator_name(instance_id: int) -> str:
    """The internal handoff-routing name for one instance's collaborator
    agent — stable and identifier-safe, unlike its free-text display_name."""
    return f"agent_{instance_id}"


MENTION_PATTERN = re.compile(r"^@(\S+)\s*(.*)$", re.DOTALL)


def _normalize_mention(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def resolve_mention(message: str, instances: list[dict]) -> tuple[dict | None, str]:
    """A cheaper alternative to the full "Add Agent" fixed-collaborator
    roster: within the homepage's shared chat, a message starting with
    "@SomeAgentName ..." addresses that one specific included agent
    directly instead of leaving every message to the supervisor's own
    routing guess — matching real watsonx Orchestrate's per-message
    assistant_id/mentions concept.

    Matches the mention token against each candidate's display_name,
    case- and punctuation-insensitively (so "@compliance" matches
    "Compliance report "). Returns (that instance, the message with the
    mention stripped) only when exactly one instance matches and there's
    still a real question left after the mention — an ambiguous, no-match,
    or mention-only message falls back to (None, message unchanged) so the
    supervisor's normal auto-routing takes over exactly as if no @ were
    typed, rather than guessing which agent was meant."""
    match = MENTION_PATTERN.match(message.strip())
    if not match:
        return None, message
    token, rest = match.group(1), match.group(2)
    if not rest.strip():
        return None, message
    normalized_token = _normalize_mention(token)
    if not normalized_token:
        return None, message
    candidates = [
        instance
        for instance in instances
        if normalized_token in _normalize_mention(instance["display_name"])
    ]
    if len(candidates) == 1:
        return candidates[0], rest
    return None, message


def _routing_prompt(instances: list[dict]) -> str:
    lines = [
        "You are the routing supervisor for a mutual fund's agent "
        "platform. Route each question to exactly one of the specialists "
        "below and let them answer — never try to answer using your own "
        "knowledge:",
    ]
    for instance in instances:
        lines.append(
            f"- {collaborator_name(instance['id'])} ({instance['display_name']}): "
            f"{instance['description'] or 'No description provided.'}"
        )
    return "\n".join(lines)


def build_chat_supervisor(
    instances: list[dict],
    workflow_configs: dict[str, WorkflowConfig],
    checkpointer: BaseCheckpointSaver,
):
    """Ad hoc Q&A entry point for the homepage chat. Routes across whichever
    deployed agent instances the user has chosen to include (the chat's
    "Manage agents" picker, backed by each instance's included_in_chat flag)
    — each collaborator is built exactly the way that agent's own chat is
    (own tools, own description-driven prompt), so this stays generic across
    any template rather than hardcoding which agents exist. With none
    selected, falls back to a plain, ungrounded conversational agent instead
    of a supervisor with nothing to route to."""
    model = init_chat_model(
        settings.aggregation_model, timeout=LLM_TIMEOUT_SECONDS, max_retries=LLM_MAX_RETRIES
    )

    if not instances:
        return create_agent(
            model, tools=None, system_prompt=NO_AGENTS_SYSTEM_PROMPT, checkpointer=checkpointer
        )

    collaborators = [
        build_instance_agent(
            instance,
            workflow_configs[instance["template_name"]],
            name=collaborator_name(instance["id"]),
            checkpointer=checkpointer,
            include_report_tool=True,
        )
        for instance in instances
    ]
    supervisor = create_supervisor(
        collaborators,
        model=model,
        prompt=_routing_prompt(instances),
        # Needed so a collaborator's own generate_report tool call is
        # visible in the supervisor's message state — the default
        # "last_message" mode trims a collaborator's turn down to just its
        # final reply, which drops the ToolMessage main.py checks for to
        # know a report just went pending (rather than an old one from
        # several turns ago) resurfacing on an unrelated question.
        output_mode="full_history",
    )
    return supervisor.compile(checkpointer=checkpointer)


def extract_routed_to(messages: list) -> str | None:
    """Read which collaborator most recently handled the conversation, off
    the handoff ToolMessage langgraph-supervisor tags automatically —
    rather than guessing from the answer text. None when nothing handed off
    (including the no-agents plain-chat fallback, which never routes)."""
    for message in reversed(messages):
        destination = getattr(message, "response_metadata", {}).get(
            METADATA_KEY_HANDOFF_DESTINATION
        )
        if destination:
            return destination
    return None


def extract_final_answer(messages: list, collaborator_names: set[str]) -> str:
    """Return the collaborator's actual answer, not whatever the supervisor
    says afterward once it regains control — after a handoff, the
    supervisor takes another turn and often adds its own short (and often
    vague) wrap-up rather than repeating the collaborator's real answer, so
    the true last message in `messages` isn't reliably "the answer". Falls
    through to the last message directly for the no-agents plain-chat case,
    where collaborator_names is empty and there's no handoff at all."""
    for message in reversed(messages):
        if getattr(message, "response_metadata", {}).get(
            METADATA_KEY_IS_HANDOFF_BACK
        ):
            continue
        if getattr(message, "name", None) in collaborator_names:
            return extract_text(message)
    return extract_text(messages[-1])
