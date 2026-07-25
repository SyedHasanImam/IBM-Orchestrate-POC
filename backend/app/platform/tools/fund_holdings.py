import openpyxl
from langchain_core.tools import tool

from app.core.config import DATA_DIR

FUND_HOLDINGS_PATH = DATA_DIR / "mock" / "fund_holdings" / "fund_holdings_dataset.xlsx"


@tool
def get_fund_holdings() -> list[dict]:
    """Retrieve the fund's current portfolio holdings.

    Returns one entry per position (including cash and other assets), each
    with: security_id, security_name, issuer, sector, asset_class, quantity,
    price_per_unit_pkr, market_value_pkr, and weight_pct (percentage of the
    fund's net assets).
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
