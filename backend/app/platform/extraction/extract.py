import base64
import io
import json

import openpyxl
from langchain.chat_models import init_chat_model

from app.core.config import LLM_MAX_RETRIES, LLM_TIMEOUT_SECONDS, settings
from app.platform.extraction.schema import (
    CorporateActionExtractionResult,
    CorporateActionRow,
    CustodianStatementExtractionResult,
    CustodianStatementRow,
    ExtractionResult,
    LedgerExtractionResult,
    LedgerRow,
    TradeBlotterExtractionResult,
    TradeBlotterRow,
)

SYSTEM_PROMPT = (
    "You are extracting a mutual fund's portfolio holdings for this "
    "reporting period into a canonical schema. Each holding needs: "
    "security_id, security_name, issuer, sector, asset_class, quantity, "
    "price_per_unit_pkr, market_value_pkr, weight_pct. Cash, receivables, "
    "and other non-security asset-class rows legitimately have no "
    "meaningful per-unit quantity or price — if quantity or "
    "price_per_unit_pkr is blank, 'N/A', or absent for one of those rows, "
    "set it to null; that is correct, not a warning. For actual securities "
    "(e.g. Equity, Sukuk), if a required field is missing, blank, or "
    "doesn't parse as the expected type, do NOT guess or invent a value — "
    "leave that row out of `holdings` entirely and instead add an entry to "
    "`warnings` naming the row (by security_id/security_name if available, "
    "otherwise its position) and the specific field and issue."
)


def _extraction_model():
    return init_chat_model(
        settings.aggregation_model,
        timeout=LLM_TIMEOUT_SECONDS,
        max_retries=LLM_MAX_RETRIES,
    ).with_structured_output(ExtractionResult)


def extract_holdings_from_excel(raw_bytes: bytes) -> ExtractionResult:
    """Parse rows deterministically first (so numbers are never
    LLM-transcribed), then have the model map arbitrary column headers onto
    the canonical schema and flag anything missing or malformed."""
    workbook = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    header = rows[0]
    records = [
        dict(zip(header, row))
        for row in rows[1:]
        if any(value is not None for value in row)
    ]

    user_message = {
        "role": "user",
        "content": (
            "Here are the raw parsed rows from this period's holdings "
            "spreadsheet (column headers may not exactly match the "
            "canonical schema — map them sensibly):\n\n"
            + json.dumps(records, default=str)
        ),
    }
    return _extraction_model().invoke(
        [{"role": "system", "content": SYSTEM_PROMPT}, user_message]
    )


def extract_holdings_from_pdf(raw_bytes: bytes) -> ExtractionResult:
    user_message = {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": "Extract this period's holdings from the attached document.",
            },
            {
                "type": "file",
                "base64": base64.b64encode(raw_bytes).decode("ascii"),
                "mime_type": "application/pdf",
            },
        ],
    }
    return _extraction_model().invoke(
        [{"role": "system", "content": SYSTEM_PROMPT}, user_message]
    )


SUPPORTED_EXTENSIONS = (".xlsx", ".pdf")


def extract_holdings(filename: str, raw_bytes: bytes) -> ExtractionResult:
    lower = filename.lower()
    if lower.endswith(".xlsx"):
        return extract_holdings_from_excel(raw_bytes)
    if lower.endswith(".pdf"):
        return extract_holdings_from_pdf(raw_bytes)
    raise ValueError(
        f"Unsupported holdings document type: {filename} "
        f"(expected one of {SUPPORTED_EXTENSIONS})"
    )


# Each reconciliation document type gets its own canonical row schema (the
# fields genuinely differ — a trade blotter isn't shaped like a custodian
# statement) but shares one deterministic-parse-then-LLM-map-columns
# extraction path, same as holdings above. `extra_guidance` covers
# doc-type-specific exceptions the shared prompt below can't know about.
RECONCILIATION_DOCUMENT_TYPES = {
    "ledger": (
        LedgerRow,
        LedgerExtractionResult,
        "a mutual fund's internal ledger positions (its own book of record)",
        "Cash and receivable lines (security_id starting with CASH- or "
        "RECV-, or security_name indicating cash/receivables) legitimately "
        "have no meaningful quantity, cost_basis_pkr, or "
        "unrealized_gain_loss_pkr — if any of those fields is blank, 'N/A', "
        "or absent for one of those rows, set it to null; that is correct, "
        "not a warning. Only flag an actual security's row this way if a "
        "required field is genuinely missing or malformed.",
    ),
    "custodian_statement": (
        CustodianStatementRow,
        CustodianStatementExtractionResult,
        "a mutual fund's custodian statement of securities actually held in custody",
        "",
    ),
    "trade_blotter": (
        TradeBlotterRow,
        TradeBlotterExtractionResult,
        "a mutual fund's trade blotter of buy/sell trades and their settlement status",
        "",
    ),
    "corporate_actions": (
        CorporateActionRow,
        CorporateActionExtractionResult,
        "a mutual fund's corporate actions calendar (dividends, bonus/rights issues, etc.)",
        "credit_date is legitimately 'N/A' for corporate actions that don't "
        "involve a share credit (e.g. a cash dividend) — set it to null in "
        "that case; that is correct, not a warning.",
    ),
}


def extract_reconciliation_document(doc_type: str, filename: str, raw_bytes: bytes):
    """Parse rows deterministically first (so numbers are never LLM-
    transcribed), then have the model map arbitrary column headers onto the
    canonical schema for this reconciliation document type and flag
    anything missing or malformed."""
    if doc_type not in RECONCILIATION_DOCUMENT_TYPES:
        raise ValueError(f"Unknown reconciliation document type: {doc_type}")
    if not filename.lower().endswith(".xlsx"):
        raise ValueError(
            f"Unsupported file type for {doc_type}: {filename} (expected .xlsx)"
        )

    row_model, result_model, description, extra_guidance = RECONCILIATION_DOCUMENT_TYPES[
        doc_type
    ]
    system_prompt = (
        f"You are extracting {description} into a canonical schema. Each "
        f"row needs: {', '.join(row_model.model_fields)}. If a required "
        "field is missing, blank, or doesn't parse as the expected type, do "
        "NOT guess or invent a value — leave that row out of `rows` "
        "entirely and instead add an entry to `warnings` naming the row (by "
        "its most identifying field if available, otherwise its position) "
        "and the specific field and issue."
        + (f" {extra_guidance}" if extra_guidance else "")
    )

    workbook = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    header = rows[0]
    records = [
        dict(zip(header, row))
        for row in rows[1:]
        if any(value is not None for value in row)
    ]

    user_message = {
        "role": "user",
        "content": (
            "Here are the raw parsed rows from this document (column "
            "headers may not exactly match the canonical schema — map them "
            "sensibly):\n\n" + json.dumps(records, default=str)
        ),
    }
    model = init_chat_model(
        settings.aggregation_model, timeout=LLM_TIMEOUT_SECONDS, max_retries=LLM_MAX_RETRIES
    ).with_structured_output(result_model)
    return model.invoke([{"role": "system", "content": system_prompt}, user_message])
