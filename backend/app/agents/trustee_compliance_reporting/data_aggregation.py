from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.core.config import settings
from app.platform.tools.fund_holdings import get_fund_holdings

SYSTEM_PROMPT = (
    "You are the Data Aggregation Agent for a mutual fund's monthly trustee "
    "compliance reporting workflow. Retrieve the fund's current portfolio "
    "holdings using the get_fund_holdings tool and report back an accurate "
    "summary of what you find. Always state the exact number of holding "
    "positions when asked, and name specific securities when asked about "
    "them."
)


def build_data_aggregation_agent(checkpointer: BaseCheckpointSaver | None):
    model = init_chat_model(settings.aggregation_model)
    return create_agent(
        model,
        tools=[get_fund_holdings],
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
