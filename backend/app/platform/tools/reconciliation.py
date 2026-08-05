from collections import defaultdict

import openpyxl
from langchain_core.tools import tool

from app.core.config import DATA_DIR
from app.platform.instances.store import get_instance

FUND_LEDGER_PATH = DATA_DIR / "mock" / "fund_ledger" / "fund_ledger_dataset.xlsx"
CUSTODIAN_STATEMENT_PATH = (
    DATA_DIR / "mock" / "custodian_statements" / "custodian_statement_dataset.xlsx"
)
TRADE_BLOTTER_PATH = DATA_DIR / "mock" / "trade_blotter" / "trade_blotter.xlsx"
CORPORATE_ACTIONS_PATH = (
    DATA_DIR / "mock" / "trade_blotter" / "corporate_actions_calendar.xlsx"
)

# Cash and receivable lines are internal AMC bookkeeping entries, not
# custodied securities — a custodian statement never lists them, so they're
# excluded from position matching rather than reported as breaks.
NON_CUSTODY_PREFIXES = ("CASH-", "RECV-")


def _read_sheet(path) -> list[dict]:
    workbook = openpyxl.load_workbook(path, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    header = rows[0]
    return [
        dict(zip(header, row))
        for row in rows[1:]
        if any(value is not None for value in row)
    ]


@tool
def get_fund_ledger() -> list[dict]:
    """Retrieve the fund's internal ledger positions — the AMC's own book
    of record. Includes non-security lines like cash and receivables.

    Returns:
        One dict per position, each with security_id, security_name,
        quantity, cost_basis_pkr, market_value_pkr,
        unrealized_gain_loss_pkr, weight_pct, and book_source.
    """
    return _read_sheet(FUND_LEDGER_PATH)


@tool
def get_custodian_statement() -> list[dict]:
    """Retrieve the custodian's (CDC) statement of securities actually held
    in custody for the fund. Only covers custodied securities — cash and
    receivables are never listed here.

    Returns:
        One dict per custodied security, each with security_id,
        security_name, quantity, price_per_unit_pkr, market_value_pkr,
        custody_source, and statement_date.
    """
    return _read_sheet(CUSTODIAN_STATEMENT_PATH)


@tool
def get_trade_blotter() -> list[dict]:
    """Retrieve this period's trade blotter — every buy/sell trade the fund
    executed, with its settlement status.

    Returns:
        One dict per trade, each with trade_id, trade_date, security_id,
        security_name, side, quantity, status, and settlement_date.
    """
    return _read_sheet(TRADE_BLOTTER_PATH)


@tool
def get_corporate_actions() -> list[dict]:
    """Retrieve this period's corporate actions calendar (dividends, bonus
    issues, rights issues, etc.) for securities the fund holds.

    Returns:
        One dict per action, each with security_id, security_name,
        action_type, announcement_date, books_closure_date, credit_date,
        and details.
    """
    return _read_sheet(CORPORATE_ACTIONS_PATH)


def _instance_reconciliation_rows(instance_id: int, doc_type: str) -> list[dict]:
    instance = get_instance(instance_id)
    inputs = (instance and instance.get("reconciliation_inputs")) or {}
    return (inputs.get(doc_type) or {}).get("rows", [])


def make_get_fund_ledger_tool(instance_id: int):
    """Build a get_fund_ledger tool bound to one agent instance's own
    uploaded ledger (via its Knowledge tab), instead of the shared fixed
    mock file."""

    @tool
    def get_fund_ledger() -> list[dict]:
        """Retrieve the fund's internal ledger positions — the AMC's own
        book of record. Includes non-security lines like cash and
        receivables.

        Returns:
            One dict per position, each with security_id, security_name,
            quantity, cost_basis_pkr, market_value_pkr,
            unrealized_gain_loss_pkr, weight_pct, and book_source.
        """
        return _instance_reconciliation_rows(instance_id, "ledger")

    return get_fund_ledger


def make_get_custodian_statement_tool(instance_id: int):
    """Build a get_custodian_statement tool bound to one agent instance's
    own uploaded custodian statement, instead of the shared fixed mock
    file."""

    @tool
    def get_custodian_statement() -> list[dict]:
        """Retrieve the custodian's (CDC) statement of securities actually
        held in custody for the fund. Only covers custodied securities —
        cash and receivables are never listed here.

        Returns:
            One dict per custodied security, each with security_id,
            security_name, quantity, price_per_unit_pkr, market_value_pkr,
            custody_source, and statement_date.
        """
        return _instance_reconciliation_rows(instance_id, "custodian_statement")

    return get_custodian_statement


def make_get_trade_blotter_tool(instance_id: int):
    """Build a get_trade_blotter tool bound to one agent instance's own
    uploaded trade blotter, instead of the shared fixed mock file."""

    @tool
    def get_trade_blotter() -> list[dict]:
        """Retrieve this period's trade blotter — every buy/sell trade the
        fund executed, with its settlement status.

        Returns:
            One dict per trade, each with trade_id, trade_date,
            security_id, security_name, side, quantity, status, and
            settlement_date.
        """
        return _instance_reconciliation_rows(instance_id, "trade_blotter")

    return get_trade_blotter


def make_get_corporate_actions_tool(instance_id: int):
    """Build a get_corporate_actions tool bound to one agent instance's own
    uploaded corporate actions calendar, instead of the shared fixed mock
    file."""

    @tool
    def get_corporate_actions() -> list[dict]:
        """Retrieve this period's corporate actions calendar (dividends,
        bonus issues, rights issues, etc.) for securities the fund holds.

        Returns:
            One dict per action, each with security_id, security_name,
            action_type, announcement_date, books_closure_date,
            credit_date, and details.
        """
        return _instance_reconciliation_rows(instance_id, "corporate_actions")

    return get_corporate_actions


def make_match_positions_tool(instance_id: int):
    """Build a match_positions tool bound to one agent instance's own
    uploaded reconciliation documents, mirroring the other
    make_*_tool factories' per-instance scoping. Any document slot that
    hasn't been uploaded yet is simply empty — trade blotter and corporate
    actions are optional, so their absence just means fewer breaks get
    auto-explained rather than an error."""

    @tool
    def match_positions() -> dict:
        """Compare the fund's internal ledger against the custodian's
        statement, position by position. For each break, attempts a
        deterministic explanation using the trade blotter (a pending
        settlement can explain a position missing from the custodian
        statement) or the corporate actions calendar (a bonus/split action
        can explain a quantity difference) — breaks with no such match are
        'unexplained' and need investigation. Figures are computed
        deterministically — use them exactly as given, never round,
        estimate, or recompute them.

        Returns:
            A dict with data_available — if False, neither the ledger nor
            custodian statement have been uploaded and break_count is
            meaningless; tell the user that data instead of reporting "0
            breaks". If True, matched_position_count, break_count, and
            breaks (one entry per break — security_id, security_name,
            ledger_quantity, custodian_quantity, quantity_difference,
            status "explained"/"unexplained", explanation_type, and
            explanation_detail).
        """
        return compute_position_matches(
            ledger=_instance_reconciliation_rows(instance_id, "ledger"),
            custodian=_instance_reconciliation_rows(instance_id, "custodian_statement"),
            trade_blotter=_instance_reconciliation_rows(instance_id, "trade_blotter"),
            corporate_actions=_instance_reconciliation_rows(instance_id, "corporate_actions"),
        )

    return match_positions


def _to_float(value) -> float:
    return float(value) if value is not None else 0.0


def compute_position_matches(
    ledger: list[dict],
    custodian: list[dict],
    trade_blotter: list[dict],
    corporate_actions: list[dict],
) -> dict:
    """Deterministically match the fund's internal ledger against the
    custodian's statement, position by position, and attempt to explain any
    quantity break using the trade blotter (a pending settlement can explain
    a position missing from the custodian statement) or the corporate
    actions calendar (a bonus/split action can explain a quantity
    difference). Kept as plain, non-LLM computation so the exact quantities
    and differences are never left to the model to estimate or recompute.

    If both the ledger and custodian statement are empty, skips matching
    entirely rather than returning "0 breaks" — with nothing on either
    side to compare, that reads as a clean reconciliation when it's really
    that no data has been uploaded at all.
    """
    if not ledger and not custodian:
        return {
            "matched_position_count": 0,
            "break_count": 0,
            "breaks": [],
            "data_available": False,
        }

    ledger_by_id = {
        row["security_id"]: row
        for row in ledger
        if not str(row["security_id"]).startswith(NON_CUSTODY_PREFIXES)
    }
    custodian_by_id = {row["security_id"]: row for row in custodian}

    pending_trades_by_id: dict[str, list[dict]] = defaultdict(list)
    for trade in trade_blotter:
        if trade.get("status") == "PENDING SETTLEMENT":
            pending_trades_by_id[trade["security_id"]].append(trade)

    bonus_actions_by_id: dict[str, list[dict]] = defaultdict(list)
    for action in corporate_actions:
        action_type = str(action.get("action_type") or "")
        if "Bonus" in action_type or "Split" in action_type:
            bonus_actions_by_id[action["security_id"]].append(action)

    all_ids = sorted(set(ledger_by_id) | set(custodian_by_id))
    breaks = []
    matched_count = 0

    for security_id in all_ids:
        ledger_row = ledger_by_id.get(security_id)
        custodian_row = custodian_by_id.get(security_id)
        ledger_qty = _to_float(ledger_row["quantity"]) if ledger_row else None
        custodian_qty = _to_float(custodian_row["quantity"]) if custodian_row else None
        quantity_difference = (ledger_qty or 0.0) - (custodian_qty or 0.0)

        if ledger_row and custodian_row and quantity_difference == 0:
            matched_count += 1
            continue

        pending = pending_trades_by_id.get(security_id)
        bonus_actions = bonus_actions_by_id.get(security_id)
        if pending:
            explanation_type, explanation_detail = "pending_settlement", pending[0]
        elif bonus_actions:
            explanation_type, explanation_detail = "corporate_action", bonus_actions[0]
        else:
            explanation_type, explanation_detail = None, None

        breaks.append(
            {
                "security_id": security_id,
                "security_name": (ledger_row or custodian_row)["security_name"],
                "ledger_quantity": ledger_qty,
                "custodian_quantity": custodian_qty,
                "quantity_difference": round(quantity_difference, 2),
                "status": "explained" if explanation_type else "unexplained",
                "explanation_type": explanation_type,
                "explanation_detail": explanation_detail,
            }
        )

    return {
        "matched_position_count": matched_count,
        "break_count": len(breaks),
        "breaks": breaks,
        "data_available": True,
    }


@tool
def match_positions() -> dict:
    """Compare the fund's internal ledger against the custodian's
    statement, position by position. For each break, attempts a
    deterministic explanation using the trade blotter (a pending
    settlement can explain a position missing from the custodian
    statement) or the corporate actions calendar (a bonus/split action can
    explain a quantity difference) — breaks with no such match are
    'unexplained' and need investigation. Figures are computed
    deterministically — use them exactly as given, never round, estimate,
    or recompute them.

    Returns:
        A dict with data_available — if False, neither the ledger nor
        custodian statement have been uploaded and break_count is
        meaningless; tell the user that data instead of reporting "0
        breaks". If True, matched_position_count, break_count, and breaks
        (one entry per break — security_id, security_name,
        ledger_quantity, custodian_quantity, quantity_difference, status
        "explained"/"unexplained", explanation_type, and
        explanation_detail).
    """
    return compute_position_matches(
        ledger=get_fund_ledger.invoke({}),
        custodian=get_custodian_statement.invoke({}),
        trade_blotter=get_trade_blotter.invoke({}),
        corporate_actions=get_corporate_actions.invoke({}),
    )
