import openpyxl
from langchain_core.tools import tool

from app.core.config import DATA_DIR
from app.platform.instances.store import get_instance

FUND_HOLDINGS_PATH = DATA_DIR / "mock" / "fund_holdings" / "fund_holdings_dataset.xlsx"


@tool
def get_fund_holdings() -> list[dict]:
    """Retrieve the fund's current portfolio holdings.

    Returns:
        One dict per position (including cash and other assets), each with
        security_id, security_name, issuer, sector, asset_class, quantity,
        price_per_unit_pkr, market_value_pkr, and weight_pct (percentage of
        the fund's net assets).
    """
    workbook = openpyxl.load_workbook(FUND_HOLDINGS_PATH, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    header = rows[0]
    return [
        dict(zip(header, row))
        for row in rows[1:]
        if any(value is not None for value in row)
    ]


def make_get_fund_holdings_tool(instance_id: int):
    """Build a get_fund_holdings tool bound to one agent instance's own
    holdings snapshot (uploaded once via its Knowledge tab), instead of the
    shared fixed mock file — so a report reflects whatever holdings that
    specific agent currently has attached."""

    @tool
    def get_fund_holdings() -> list[dict]:
        """Retrieve the fund's current portfolio holdings.

        Returns:
            One dict per position (including cash and other assets), each
            with security_id, security_name, issuer, sector, asset_class,
            quantity, price_per_unit_pkr, market_value_pkr, and weight_pct
            (percentage of the fund's net assets).
        """
        instance = get_instance(instance_id)
        return (instance and instance.get("holdings_snapshot")) or []

    return get_fund_holdings
