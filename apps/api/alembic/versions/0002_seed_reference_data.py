"""seed reference data — 5 formats and 3 currencies

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-24

Reference data the system needs to function (formats and currencies). Operational
seed data — retailers, suppliers, sample orders, feedbacks — comes from the
seed endpoint in Phase 5.4.
"""
from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


FORMATS = [
    ("json", "JSON — stdlib parser"),
    ("xml", "XML — lxml + XPath, Facturae-flavoured PO schema"),
    ("csv", "CSV — pandas multi-row aggregation"),
    ("edifact", "EDIFACT D.96A ORDERS — pydifact"),
    ("pdf", "PDF — multimodal Parser Agent (Claude)"),
]

# code, iso_number, symbol, decimal_points
CURRENCIES = [
    ("USD", "840", "$", 2),
    ("EUR", "978", "€", 2),
    ("GBP", "826", "£", 2),
]


def upgrade() -> None:
    formats_table = sa.table(
        "formats",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("description", sa.String()),
    )
    op.bulk_insert(
        formats_table,
        [{"id": uuid4(), "code": code, "description": desc} for code, desc in FORMATS],
    )

    currencies_table = sa.table(
        "currencies",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("iso_number", sa.String()),
        sa.column("symbol", sa.String()),
        sa.column("decimal_points", sa.Integer()),
    )
    op.bulk_insert(
        currencies_table,
        [
            {
                "id": uuid4(),
                "code": code,
                "iso_number": iso_number,
                "symbol": symbol,
                "decimal_points": dp,
            }
            for code, iso_number, symbol, dp in CURRENCIES
        ],
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM currencies WHERE code IN ('USD', 'EUR', 'GBP')")
    )
    bind.execute(
        sa.text(
            "DELETE FROM formats WHERE code IN ('json', 'xml', 'csv', 'edifact', 'pdf')"
        )
    )
