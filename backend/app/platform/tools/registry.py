from app.platform.rag.retrieval import search_compliance_kb
from app.platform.tools.exposure_summary import get_portfolio_exposure_summary
from app.platform.tools.fund_holdings import get_fund_holdings

TOOL_REGISTRY = {
    "get_fund_holdings": get_fund_holdings,
    "get_portfolio_exposure_summary": get_portfolio_exposure_summary,
    "search_compliance_kb": search_compliance_kb,
}
