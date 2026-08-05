from langchain_core.tools import tool

from app.platform.tools.exposure_summary import (
    compute_exposure_summary,
    make_get_portfolio_exposure_summary_tool,
)
from app.platform.tools.fund_holdings import get_fund_holdings

# Numeric thresholds and citations, taken verbatim from the fund's actual
# Investment Mandate (data/mock/compliance_docs/investment_mandate.md).
# Keeping the threshold and its citation paired together in one rule table
# — rather than having the LLM retrieve the citation text separately via
# search_compliance_kb and compare it against the figure itself — is the
# actual fix here: BREACH/PASS becomes a code comparison, not LLM judgment.
# If the mandate is ever amended, this table is the one place to update.
MIN_EQUITY_ALLOCATION_PCT = 70.0
EQUITY_ALLOCATION_CITATION = "Clause 5.1 — Minimum Equity Allocation"

SINGLE_ISSUER_LIMIT_PCT = 10.0
SINGLE_ISSUER_CITATION = "Clause 6.1 — Single Entity Exposure Limit"

SINGLE_SECTOR_LIMIT_PCT = 20.0
SINGLE_SECTOR_CITATION = "Clause 6.2 — Single Sector Exposure Limit"

SHARIAH_CITATION = "Clause 6.3 — Shariah Compliance Restriction"
# The Shariah Advisor's own non-compliant list is what real Islamic funds
# maintain and update as holdings change — sector labels alone can't stand
# in for it (this fund's own holdings file, for example, files a real
# Islamic bank and a conventional bank under the identical sector label
# "Commercial Banks"). This static list is this POC's stand-in for that
# advisor-maintained list; it isn't derived from sector or asset class.
SHARIAH_NON_COMPLIANT_ISSUERS = {
    "Bank Al Habib Limited",
    "Adamjee Insurance Company Limited",
}

MIN_LIQUIDITY_PCT = 5.0
LIQUIDITY_CITATION = "Clause 7.1 — Minimum Liquidity Requirement"

# "Other" is this dataset's catch-all bucket for holdings that don't map to
# a specific PSX sector classification (e.g. mixed industrials) — it isn't
# itself a single PSX-classified sector, so Clause 6.2's single-sector limit
# doesn't apply to it directly. Excluded from that check, but its own total
# is still surfaced in the result so a real concentration in that bucket
# isn't silently dropped.
UNCLASSIFIED_SECTOR_KEY = "Other"


def compute_compliance_checks(exposure_summary: dict) -> dict:
    """Deterministically evaluate the fund's portfolio exposures against the
    Investment Mandate's five compliance checks. Kept as plain, non-LLM
    comparison — same reasoning as compute_position_matches for
    reconciliation — so BREACH/PASS is never left to the model to judge or
    misread from retrieved text."""
    sector_totals = exposure_summary["sector_totals"]
    largest_issuer = exposure_summary["largest_single_issuer"]
    holdings = exposure_summary["holdings"]

    checks = []

    if largest_issuer:
        figure = largest_issuer["weight_pct"]
        checks.append(
            {
                "check": "single_issuer_exposure",
                "figure_pct": figure,
                "limit_pct": SINGLE_ISSUER_LIMIT_PCT,
                "limit_type": "max",
                "status": "BREACH" if figure > SINGLE_ISSUER_LIMIT_PCT else "PASS",
                "citation": SINGLE_ISSUER_CITATION,
                "detail": f"{largest_issuer['security_name']} at {figure}% of Net Assets",
            }
        )

    classified_sectors = {
        sector: weight
        for sector, weight in sector_totals.items()
        if sector != UNCLASSIFIED_SECTOR_KEY
    }
    if classified_sectors:
        largest_sector, figure = max(classified_sectors.items(), key=lambda kv: kv[1])
        detail = f"{largest_sector} at {figure}% of Net Assets"
        if UNCLASSIFIED_SECTOR_KEY in sector_totals:
            detail += (
                f" (excludes {sector_totals[UNCLASSIFIED_SECTOR_KEY]}% held under the "
                f"unclassified '{UNCLASSIFIED_SECTOR_KEY}' bucket, which is not a single "
                "PSX-classified sector)"
            )
        checks.append(
            {
                "check": "single_sector_exposure",
                "figure_pct": figure,
                "limit_pct": SINGLE_SECTOR_LIMIT_PCT,
                "limit_type": "max",
                "status": "BREACH" if figure > SINGLE_SECTOR_LIMIT_PCT else "PASS",
                "citation": SINGLE_SECTOR_CITATION,
                "detail": detail,
            }
        )

    flagged = [
        {"security_name": h["security_name"], "issuer": h["issuer"], "weight_pct": h["weight_pct"]}
        for h in holdings
        if h.get("issuer") in SHARIAH_NON_COMPLIANT_ISSUERS
    ]
    checks.append(
        {
            "check": "shariah_compliance",
            "figure_pct": None,
            "limit_pct": None,
            "limit_type": None,
            "status": "BREACH" if flagged else "PASS",
            "citation": SHARIAH_CITATION,
            "detail": (
                ", ".join(f"{f['security_name']} ({f['weight_pct']}%)" for f in flagged)
                if flagged
                else "No holdings matched against the Shariah Advisor's non-compliant list"
            ),
        }
    )

    liquidity_figure = exposure_summary["liquidity_pct"]
    checks.append(
        {
            "check": "minimum_liquidity",
            "figure_pct": liquidity_figure,
            "limit_pct": MIN_LIQUIDITY_PCT,
            "limit_type": "min",
            "status": "BREACH" if liquidity_figure < MIN_LIQUIDITY_PCT else "PASS",
            "citation": LIQUIDITY_CITATION,
            "detail": f"{liquidity_figure}% held in cash/near-cash instruments",
        }
    )

    equity_figure = exposure_summary["equity_allocation_pct"]
    checks.append(
        {
            "check": "minimum_equity_allocation",
            "figure_pct": equity_figure,
            "limit_pct": MIN_EQUITY_ALLOCATION_PCT,
            "limit_type": "min",
            "status": "BREACH" if equity_figure < MIN_EQUITY_ALLOCATION_PCT else "PASS",
            "citation": EQUITY_ALLOCATION_CITATION,
            "detail": f"{equity_figure}% of Net Assets in listed equity securities",
        }
    )

    return {
        "checks": checks,
        "breach_count": sum(1 for c in checks if c["status"] == "BREACH"),
    }


@tool
def check_compliance_limits() -> dict:
    """Check the fund's current portfolio exposures against the Investment
    Mandate's five compliance limits (single-issuer, single-sector, Shariah
    compliance, minimum liquidity, minimum equity allocation) — all
    computed deterministically in code. Use this as the sole source for
    BREACH/PASS determinations and citations when drafting the compliance
    report; never judge or recompute a verdict yourself from retrieved
    mandate text.

    Returns:
        A dict with "checks" (one entry per limit — check name, figure_pct,
        limit_pct, limit_type, status "BREACH"/"PASS", citation, and a
        human-readable detail) and "breach_count".
    """
    holdings = get_fund_holdings.invoke({})
    return compute_compliance_checks(compute_exposure_summary(holdings))


def make_check_compliance_limits_tool(instance_id: int):
    """Build a check_compliance_limits tool bound to one agent instance's
    own holdings snapshot, mirroring the other make_*_tool factories'
    per-instance scoping."""

    @tool
    def check_compliance_limits() -> dict:
        """Check the fund's current portfolio exposures against the
        Investment Mandate's five compliance limits (single-issuer,
        single-sector, Shariah compliance, minimum liquidity, minimum
        equity allocation) — all computed deterministically in code. Use
        this as the sole source for BREACH/PASS determinations and
        citations when drafting the compliance report; never judge or
        recompute a verdict yourself from retrieved mandate text.

        Returns:
            A dict with "checks" (one entry per limit — check name,
            figure_pct, limit_pct, limit_type, status "BREACH"/"PASS",
            citation, and a human-readable detail) and "breach_count".
        """
        exposure_summary = make_get_portfolio_exposure_summary_tool(instance_id).invoke({})
        return compute_compliance_checks(exposure_summary)

    return check_compliance_limits
