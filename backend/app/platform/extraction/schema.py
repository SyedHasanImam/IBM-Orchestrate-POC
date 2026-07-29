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
