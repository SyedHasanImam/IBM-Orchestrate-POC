from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.core.config import LLM_MAX_RETRIES, LLM_TIMEOUT_SECONDS, settings
from app.platform.rag.retrieval import make_search_compliance_kb_tool
from app.platform.tools.exposure_summary import make_get_portfolio_exposure_summary_tool
from app.platform.tools.fund_holdings import make_get_fund_holdings_tool

DEFAULT_SYSTEM_PROMPT_TEMPLATE = (
    "You are {display_name}, an agent on a fund management platform. "
    "{description}\n\n"
    "Use search_compliance_kb to answer questions using the "
    "regulatory/compliance documents attached to you as Knowledge. Use "
    "get_fund_holdings and get_portfolio_exposure_summary to answer "
    "questions about the fund's currently attached holdings. If the answer "
    "isn't available through any of these, say so honestly rather than "
    "guessing."
)


def build_agent_preview_chat(instance: dict, checkpointer: BaseCheckpointSaver):
    """A standalone chat agent for one specific agent instance — lets you
    ask it anything using its own attached Knowledge and holdings, whether
    it's still a draft (the editor's Preview panel) or already deployed
    (its own page). Distinct from the multi-agent chat supervisor: there's
    no routing here, just this one agent answering with its own data."""
    system_prompt = instance.get("system_prompt_override") or DEFAULT_SYSTEM_PROMPT_TEMPLATE.format(
        display_name=instance["display_name"],
        description=instance["description"] or "No description provided.",
    )
    model = init_chat_model(
        settings.compliance_model, timeout=LLM_TIMEOUT_SECONDS, max_retries=LLM_MAX_RETRIES
    )
    tools = [
        make_search_compliance_kb_tool(instance["id"]),
        make_get_fund_holdings_tool(instance["id"]),
        make_get_portfolio_exposure_summary_tool(instance["id"]),
    ]
    return create_agent(
        model, tools=tools, system_prompt=system_prompt, checkpointer=checkpointer
    )
