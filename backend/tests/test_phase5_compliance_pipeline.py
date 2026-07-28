import pytest

from app.agents.trustee_compliance_reporting import WORKFLOW_YAML_PATH
from app.platform.rag.ingest import ingest_compliance_documents
from app.platform.runtime.checkpointer import postgres_checkpointer
from app.platform.runtime.factory import build_workflow_from_config
from app.platform.runtime.loader import load_workflow_config
from app.platform.tools.exposure_summary import get_portfolio_exposure_summary


@pytest.fixture(scope="module", autouse=True)
def ingested_kb():
    ingest_compliance_documents()
    yield


@pytest.fixture(scope="module")
def pipeline_result():
    config = load_workflow_config(WORKFLOW_YAML_PATH)
    with postgres_checkpointer() as checkpointer:
        pipeline = build_workflow_from_config(config, checkpointer)
        run_config = {"configurable": {"thread_id": "phase5-test-report"}}
        yield pipeline.invoke({}, config=run_config)


def test_exposure_summary_matches_known_ground_truth():
    # Deterministic computation, independent of any LLM call — verified
    # directly against the tool the compliance-checking agent calls.
    summary = get_portfolio_exposure_summary.invoke({})
    assert summary["largest_single_issuer"]["security_id"] == "PK0080101018"  # OGDC
    assert summary["largest_single_issuer"]["weight_pct"] == pytest.approx(11.81)
    assert summary["sector_totals"]["Oil & Gas Exploration Companies"] == pytest.approx(
        22.48
    )
    assert summary["liquidity_pct"] == pytest.approx(1.44)
    assert summary["equity_allocation_pct"] == pytest.approx(98.57)


def test_report_cites_correct_clauses_and_breach_status(pipeline_result):
    report = pipeline_result["report"]

    # Single-issuer: OGDC 11.81% vs 10% limit -> breach, Clause 6.1
    assert "6.1" in report
    assert "11.81" in report

    # Sector: Oil & Gas Exploration 22.48% vs 20% limit -> breach, Clause 6.2
    assert "6.2" in report
    assert "22.48" in report

    # Shariah: Bank Al Habib (conventional bank) -> breach, Clause 6.3
    assert "6.3" in report
    assert "Bank Al Habib" in report

    # Liquidity: 1.44% vs 5% minimum -> breach, Clause 7.1
    assert "7.1" in report
    assert "1.44" in report

    # Equity allocation: 98.57% vs 70% minimum -> pass, Clause 5.1
    assert "5.1" in report
    assert "98.57" in report

    assert report.upper().count("BREACH") >= 4
    assert "PASS" in report.upper()
