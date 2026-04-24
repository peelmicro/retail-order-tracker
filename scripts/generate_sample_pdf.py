"""Generate the purchase order sample PDF committed at samples/orders/sample-pdf.pdf.

Run from the repo root:
    apps/api/.venv/bin/python scripts/generate_sample_pdf.py

Only the generated PDF is committed; this script exists so reviewers can
reproduce it. fpdf2 is listed as a dev-tool dependency in requirements.txt.

Uses ASCII-safe separators because fpdf2's built-in Helvetica is Latin-1 only.
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

OUTPUT_PATH = (
    Path(__file__).resolve().parents[1] / "samples" / "orders" / "sample-pdf.pdf"
)

ORDER = {
    "order_number": "PO-MERCADONA-000654",
    "order_date": "2026-04-23",
    "expected_delivery_date": "2026-04-30",
    "retailer_code": "MERCADONA-ES",
    "retailer_name": "Mercadona SA",
    "retailer_address": "C/ Valencia, 5 | 46016 Tavernes Blanques | Spain",
    "supplier_code": "BODEGAS-RIOJA",
    "supplier_name": "Bodegas Rioja SL",
    "supplier_address": "Carretera de Haro, km 3 | 26006 Logrono | Spain",
    "currency": "EUR",
    "lines": [
        # (line no, product code, name, qty, unit price EUR, line total EUR)
        (1, "WINE-RIOJA-CRIANZA-75CL", "Rioja Crianza 75cl", 120, 7.95, 954.00),
        (2, "WINE-RIOJA-RESERVA-75CL", "Rioja Reserva 75cl", 60, 14.50, 870.00),
        (3, "WINE-RIOJA-GRANRES-75CL", "Rioja Gran Reserva 75cl", 24, 28.00, 672.00),
    ],
    "total": 2496.00,
}

_LN = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}


def render_pdf(path: Path) -> None:
    pdf = FPDF(format="A4", unit="mm")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Header
    pdf.set_font("helvetica", style="B", size=18)
    pdf.cell(0, 10, "PURCHASE ORDER", align="C", **_LN)
    pdf.ln(4)

    pdf.set_font("helvetica", style="B", size=12)
    pdf.cell(0, 6, f"Order Number: {ORDER['order_number']}", **_LN)
    pdf.set_font("helvetica", size=10)
    pdf.cell(0, 5, f"Order Date: {ORDER['order_date']}", **_LN)
    pdf.cell(0, 5, f"Expected Delivery: {ORDER['expected_delivery_date']}", **_LN)
    pdf.cell(0, 5, f"Currency: {ORDER['currency']}", **_LN)
    pdf.ln(5)

    # Buyer / supplier — two side-by-side columns
    pdf.set_font("helvetica", style="B", size=11)
    pdf.cell(90, 6, "BUYER (Retailer)")
    pdf.cell(0, 6, "SUPPLIER", **_LN)
    pdf.set_font("helvetica", size=10)
    pdf.cell(90, 5, f"{ORDER['retailer_name']} [{ORDER['retailer_code']}]")
    pdf.cell(0, 5, f"{ORDER['supplier_name']} [{ORDER['supplier_code']}]", **_LN)
    pdf.cell(90, 5, ORDER["retailer_address"])
    pdf.cell(0, 5, ORDER["supplier_address"], **_LN)
    pdf.ln(6)

    # Line items table
    pdf.set_font("helvetica", style="B", size=10)
    pdf.set_fill_color(230, 230, 230)
    header_cells = [
        ("#", 10), ("Product Code", 55), ("Description", 55),
        ("Qty", 15), ("Unit Price", 25), ("Line Total", 30),
    ]
    for label, width in header_cells:
        pdf.cell(width, 7, label, border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("helvetica", size=9)
    for line_no, code, name, qty, unit_price, line_total in ORDER["lines"]:
        pdf.cell(10, 6, str(line_no), border=1, align="C")
        pdf.cell(55, 6, code, border=1)
        pdf.cell(55, 6, name, border=1)
        pdf.cell(15, 6, str(qty), border=1, align="R")
        pdf.cell(25, 6, f"EUR {unit_price:,.2f}", border=1, align="R")
        pdf.cell(30, 6, f"EUR {line_total:,.2f}", border=1, align="R")
        pdf.ln()

    # Total
    pdf.ln(3)
    pdf.set_font("helvetica", style="B", size=11)
    pdf.cell(160, 7, "Total", border=1, align="R")
    pdf.cell(30, 7, f"EUR {ORDER['total']:,.2f}", border=1, align="R")
    pdf.ln(12)

    # Footer
    pdf.set_font("helvetica", style="I", size=8)
    pdf.multi_cell(
        0,
        4,
        "This document is a sample purchase order for the retail-order-tracker "
        "assessment. All prices are in EUR. Total amount in minor units (integer "
        "cents) expected by the Parser Agent: 249600.",
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))


def main() -> None:
    render_pdf(OUTPUT_PATH)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
