from collections import defaultdict

from langchain_core.tools import tool

from app.platform.instances.store import get_instance
from app.platform.tools.fund_holdings import get_fund_holdings


def compute_exposure_summary(holdings: list[dict]) -> dict:
    """Deterministically aggregate the fund's holdings into the figures a
    compliance check needs: total weight by sector, total weight by asset
    class, the single largest equity issuer, liquidity (cash + other
    assets), and equity allocation. Kept as plain, non-LLM computation so
    the exact regulatory-relevant numbers are never left to the model to
    estimate or recompute.
    """
    sector_totals: dict[str, float] = defaultdict(float)
    asset_class_totals: dict[str, float] = defaultdict(float)
    largest_issuer: dict | None = None

    for holding in holdings:
        weight = float(holding["weight_pct"])
        sector = holding.get("sector")
        if sector:
            sector_totals[sector] += weight
        asset_class_totals[holding["asset_class"]] += weight

        if holding["asset_class"] == "Equity" and (
            largest_issuer is None or weight > largest_issuer["weight_pct"]
        ):
            largest_issuer = {
                "security_id": holding["security_id"],
                "security_name": holding["security_name"],
                "weight_pct": weight,
            }

    liquidity_pct = asset_class_totals.get("Cash", 0.0) + asset_class_totals.get(
        "Other Assets", 0.0
    )

    return {
        # False when there are no holdings at all — an empty portfolio
        # computes to all-zero figures that are indistinguishable from a
        # real (if unusual) 0% reading, so callers must check this rather
        # than inferring "no data" from zeros alone.
        "data_available": bool(holdings),
        "sector_totals": {k: round(v, 2) for k, v in sector_totals.items()},
        "asset_class_totals": {k: round(v, 2) for k, v in asset_class_totals.items()},
        "largest_single_issuer": largest_issuer,
        "liquidity_pct": round(liquidity_pct, 2),
        "equity_allocation_pct": round(asset_class_totals.get("Equity", 0.0), 2),
        "holdings": holdings,
    }


@tool
def get_portfolio_exposure_summary() -> dict:
    """Compute the fund's current portfolio exposures needed for compliance
    checks. Figures are computed deterministically from the fund's
    holdings — use them exactly as given, never round, estimate, or
    recompute them.

    Returns:
        A dict with data_available (False if no holdings are attached at
        all — check this before reporting any figure, since an empty
        portfolio computes to all-zero values indistinguishable from a
        real 0% reading), sector_totals, asset_class_totals,
        largest_single_issuer, liquidity_pct, equity_allocation_pct, and
        the raw holdings list they were computed from.
    """
    holdings = get_fund_holdings.invoke({})
    return compute_exposure_summary(holdings)


def make_get_portfolio_exposure_summary_tool(instance_id: int):
    """Build a get_portfolio_exposure_summary tool bound to one agent
    instance's own holdings snapshot, mirroring
    make_get_fund_holdings_tool's per-instance scoping."""

    @tool
    def get_portfolio_exposure_summary() -> dict:
        """Compute the fund's current portfolio exposures needed for
        compliance checks. Figures are computed deterministically from the
        fund's holdings — use them exactly as given, never round, estimate,
        or recompute them.

        Returns:
            A dict with data_available (False if no holdings are attached
            at all — check this before reporting any figure, since an
            empty portfolio computes to all-zero values indistinguishable
            from a real 0% reading), sector_totals, asset_class_totals,
            largest_single_issuer, liquidity_pct, equity_allocation_pct,
            and the raw holdings list they were computed from.
        """
        instance = get_instance(instance_id)
        holdings = (instance and instance.get("holdings_snapshot")) or []
        return compute_exposure_summary(holdings)

    return get_portfolio_exposure_summary
