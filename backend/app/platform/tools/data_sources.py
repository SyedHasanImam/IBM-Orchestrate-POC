from dataclasses import dataclass


@dataclass(frozen=True)
class DataSourceSpec:
    """One kind of document an agent's tools can read from. `kind` says
    which storage shape it lives in on agent_instances — the single
    holdings_snapshot column, or one key of the reconciliation_inputs JSONB
    map (see instances/schema.py) — so a generic upload UI/endpoint knows
    where to read and write without a template-specific branch."""

    key: str
    label: str
    description: str
    tool_names: frozenset[str]
    required: bool
    accept: tuple[str, ...]
    kind: str  # "holdings" | "reconciliation"


# The single place that says which tools need which uploaded data. Anything
# that reads/gates on "does this agent need X data" (the Knowledge tab's
# upload slots, the generate_report tool's missing-data guard) should look
# here instead of keeping its own copy of this mapping — that duplication is
# exactly what let a Compliance agent with an added ledger tool upload its
# ledger into the holdings slot and silently corrupt it.
DATA_SOURCE_REGISTRY: dict[str, DataSourceSpec] = {
    "holdings": DataSourceSpec(
        key="holdings",
        label="Holdings",
        description=(
            "This period's portfolio holdings snapshot — one row per "
            "position (security, sector, asset class, quantity, price, "
            "market value, weight). Used for compliance checks and "
            "exposure summaries."
        ),
        tool_names=frozenset({"get_fund_holdings", "get_portfolio_exposure_summary"}),
        required=True,
        accept=(".xlsx", ".pdf"),
        kind="holdings",
    ),
    "ledger": DataSourceSpec(
        key="ledger",
        label="Fund Ledger",
        description=(
            "The fund's internal ledger positions — its own book of record. "
            "Compared against the custodian statement to find breaks."
        ),
        tool_names=frozenset({"get_fund_ledger", "match_positions"}),
        required=True,
        accept=(".xlsx",),
        kind="reconciliation",
    ),
    "custodian_statement": DataSourceSpec(
        key="custodian_statement",
        label="Custodian Statement",
        description=(
            "The custodian's (CDC) statement of securities actually held in "
            "custody — compared against the ledger to find breaks."
        ),
        tool_names=frozenset({"get_custodian_statement", "match_positions"}),
        required=True,
        accept=(".xlsx",),
        kind="reconciliation",
    ),
    "trade_blotter": DataSourceSpec(
        key="trade_blotter",
        label="Trade Blotter",
        description=(
            "This period's buy/sell trades and settlement status. Optional "
            "— attaching it lets more ledger/custodian breaks get "
            "automatically explained instead of flagged as unexplained."
        ),
        tool_names=frozenset({"get_trade_blotter"}),
        required=False,
        accept=(".xlsx",),
        kind="reconciliation",
    ),
    "corporate_actions": DataSourceSpec(
        key="corporate_actions",
        label="Corporate Actions Calendar",
        description=(
            "This period's dividends, bonus issues, and rights issues. "
            "Optional — attaching it lets more breaks get automatically "
            "explained instead of flagged as unexplained."
        ),
        tool_names=frozenset({"get_corporate_actions"}),
        required=False,
        accept=(".xlsx",),
        kind="reconciliation",
    ),
}


def required_data_sources(tool_names: set[str]) -> list[DataSourceSpec]:
    """Which data sources at least one of these tools needs, in registry
    order. `tool_names` is meant to be a template's own tools unioned with
    whatever's been added via Add Tool — this is what makes an added tool's
    upload slot show up automatically."""
    return [
        spec for spec in DATA_SOURCE_REGISTRY.values() if spec.tool_names & tool_names
    ]
