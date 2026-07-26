from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.core.config import settings

SYSTEM_PROMPT = (
    "You are the Reporting Agent for a mutual fund's monthly trustee "
    "compliance reporting workflow. You will be given this month's "
    "compliance-checking findings. Compile them into a clear, "
    "well-structured trustee report with: a short executive summary "
    "(how many breaches were found), a findings section listing each check "
    "with its figure, limit, BREACH/PASS status, and cited clause/excerpt, "
    "and a closing note that this report is pending trustee review. Do not "
    "invent any figures or citations beyond what you were given."
)


def build_reporting_agent(checkpointer: BaseCheckpointSaver | None):
    model = init_chat_model(settings.reporting_model)
    return create_agent(
        model,
        tools=None,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
