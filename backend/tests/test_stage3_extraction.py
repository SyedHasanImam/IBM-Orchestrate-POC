import io

import openpyxl

from app.core.config import DATA_DIR
from app.platform.extraction.extract import (
    extract_holdings,
    extract_holdings_from_excel,
    extract_holdings_from_pdf,
)

MOCK_HOLDINGS_PATH = DATA_DIR / "mock" / "fund_holdings" / "fund_holdings_dataset.xlsx"


def _build_xlsx(rows: list[list]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    header = [
        "security_id",
        "security_name",
        "issuer",
        "sector",
        "asset_class",
        "quantity",
        "price_per_unit_pkr",
        "market_value_pkr",
        "weight_pct",
    ]
    sheet.append(header)
    for row in rows:
        sheet.append(row)
    buf = io.BytesIO()
    workbook.save(buf)
    return buf.getvalue()


def _make_minimal_pdf(lines: list[str]) -> bytes:
    """Hand-rolled minimal single-page PDF (no reportlab/pypdf dependency
    needed just for a test fixture) — one line of text per Tj operator."""
    content_ops = []
    y = 750
    for line in lines:
        escaped = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        content_ops.append(f"BT /F1 10 Tf 40 {y} Td ({escaped}) Tj ET")
        y -= 14
    content = "\n".join(content_ops).encode("latin-1")

    obj_bodies = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 612 792] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
    ]

    buf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(obj_bodies, start=1):
        offsets.append(len(buf))
        buf += f"{i} 0 obj\n".encode("latin-1") + body + b"\nendobj\n"

    xref_offset = len(buf)
    n = len(obj_bodies) + 1
    buf += f"xref\n0 {n}\n".encode("latin-1")
    buf += b"0000000000 65535 f \n"
    for off in offsets:
        buf += f"{off:010d} 00000 n \n".encode("latin-1")
    buf += (
        f"trailer\n<< /Size {n} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF"
    ).encode("latin-1")
    return bytes(buf)


def test_extract_reproduces_known_mock_holdings():
    raw_bytes = MOCK_HOLDINGS_PATH.read_bytes()
    result = extract_holdings_from_excel(raw_bytes)

    assert len(result.holdings) == 22
    assert result.warnings == []

    ogdc = next(h for h in result.holdings if h.security_id == "PK0080101018")
    assert ogdc.security_name == "Oil & Gas Development Company Limited"
    assert ogdc.asset_class == "Equity"
    assert ogdc.weight_pct == 11.81

    security_ids = {h.security_id for h in result.holdings}
    assert "CASH-001" in security_ids


def test_extract_flags_missing_field_instead_of_guessing():
    raw_bytes = _build_xlsx(
        [
            [
                "PK0080101018",
                "Oil & Gas Development Company Limited",
                "Oil & Gas Development Company Limited",
                "Oil & Gas Exploration Companies",
                "Equity",
                34473478,
                230.00,
                7928899940,
                11.81,
            ],
            [
                "PK0080301010",
                "Lucky Cement Limited",
                "Lucky Cement Limited",
                "Cement",
                "Equity",
                None,  # quantity missing — must not be guessed
                950.00,
                6000200000,
                8.94,
            ],
        ]
    )
    result = extract_holdings_from_excel(raw_bytes)

    assert len(result.holdings) == 1
    assert result.holdings[0].security_id == "PK0080101018"
    assert len(result.warnings) >= 1
    assert any(
        "PK0080301010" in w.row_reference or "Lucky Cement" in w.row_reference
        for w in result.warnings
    )


def test_extract_holdings_dispatches_by_extension():
    raw_bytes = _build_xlsx(
        [
            [
                "PK0080101018",
                "Oil & Gas Development Company Limited",
                "Oil & Gas Development Company Limited",
                "Oil & Gas Exploration Companies",
                "Equity",
                34473478,
                230.00,
                7928899940,
                11.81,
            ]
        ]
    )
    result = extract_holdings("holdings.xlsx", raw_bytes)
    assert len(result.holdings) == 1


def test_extract_holdings_from_pdf():
    pdf_bytes = _make_minimal_pdf(
        [
            "Fund Holdings - Reporting Period",
            "Security: Oil & Gas Development Company Limited",
            "Security ID: PK0080101018",
            "Issuer: Oil & Gas Development Company Limited",
            "Sector: Oil & Gas Exploration Companies",
            "Asset Class: Equity",
            "Quantity: 34473478",
            "Price per unit (PKR): 230.00",
            "Market Value (PKR): 7928899940",
            "Weight: 11.81%",
        ]
    )
    result = extract_holdings_from_pdf(pdf_bytes)
    assert len(result.holdings) == 1
    assert result.holdings[0].security_id == "PK0080101018"
