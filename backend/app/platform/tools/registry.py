from app.platform.rag.retrieval import search_compliance_kb
from app.platform.tools.exposure_summary import get_portfolio_exposure_summary
from app.platform.tools.fund_holdings import get_fund_holdings
from app.platform.tools.reconciliation import (
    get_corporate_actions,
    get_custodian_statement,
    get_fund_ledger,
    get_trade_blotter,
    match_positions,
)

TOOL_REGISTRY = {
    "get_fund_holdings": get_fund_holdings,
    "get_portfolio_exposure_summary": get_portfolio_exposure_summary,
    "search_compliance_kb": search_compliance_kb,
    "get_fund_ledger": get_fund_ledger,
    "get_custodian_statement": get_custodian_statement,
    "get_trade_blotter": get_trade_blotter,
    "get_corporate_actions": get_corporate_actions,
    "match_positions": match_positions,
}
