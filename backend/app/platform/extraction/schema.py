from pydantic import BaseModel, Field


class HoldingRow(BaseModel):
    security_id: str
    security_name: str
    issuer: str
    sector: str | None = None
    asset_class: str
    # Cash/receivable/other-asset-type positions legitimately have no
    # per-unit quantity or price — null there is correct, not a warning.
    quantity: float | None = None
    price_per_unit_pkr: float | None = None
    market_value_pkr: float
    weight_pct: float


class ExtractionWarning(BaseModel):
    row_reference: str = Field(
        description=(
            "Best available identifier for the affected row — security_id "
            "or security_name if known, otherwise its position in the "
            "document (e.g. 'row 7')."
        )
    )
    field: str
    issue: str


class ExtractionResult(BaseModel):
    holdings: list[HoldingRow]
    warnings: list[ExtractionWarning] = Field(default_factory=list)


class LedgerRow(BaseModel):
    security_id: str
    security_name: str
    # Cash/receivable book-of-record lines legitimately have no per-unit
    # quantity or cost basis — null there is correct, not a warning.
    quantity: float | None = None
    cost_basis_pkr: float | None = None
    market_value_pkr: float
    unrealized_gain_loss_pkr: float | None = None
    weight_pct: float | None = None
    book_source: str | None = None


class LedgerExtractionResult(BaseModel):
    rows: list[LedgerRow]
    warnings: list[ExtractionWarning] = Field(default_factory=list)


class CustodianStatementRow(BaseModel):
    security_id: str
    security_name: str
    quantity: float
    price_per_unit_pkr: float | None = None
    market_value_pkr: float | None = None
    custody_source: str | None = None
    statement_date: str | None = None


class CustodianStatementExtractionResult(BaseModel):
    rows: list[CustodianStatementRow]
    warnings: list[ExtractionWarning] = Field(default_factory=list)


class TradeBlotterRow(BaseModel):
    trade_id: str
    trade_date: str | None = None
    security_id: str
    security_name: str
    side: str
    quantity: float
    status: str
    settlement_date: str | None = None


class TradeBlotterExtractionResult(BaseModel):
    rows: list[TradeBlotterRow]
    warnings: list[ExtractionWarning] = Field(default_factory=list)


class CorporateActionRow(BaseModel):
    security_id: str
    security_name: str
    action_type: str
    announcement_date: str | None = None
    books_closure_date: str | None = None
    credit_date: str | None = None
    details: str | None = None


class CorporateActionExtractionResult(BaseModel):
    rows: list[CorporateActionRow]
    warnings: list[ExtractionWarning] = Field(default_factory=list)
