"""initial schema — 9 tables and 3 enums

Revision ID: 0001
Revises:
Create Date: 2026-04-23

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Enum value lists are duplicated from src.domain.enums on purpose:
# migrations must be reproducible from this file alone, with no runtime imports.
ORDER_STATUS_VALUES = (
    "pending_review",
    "approved",
    "clarification_requested",
    "escalated",
    "rejected_by_operator",
)
AGENT_ACTION_VALUES = (
    "approve",
    "request_clarification",
    "escalate",
)
OPERATOR_DECISION_VALUES = (
    "accepted",
    "modified",
    "rejected",
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    # ---- Enums --------------------------------------------------------------
    order_status = postgresql.ENUM(*ORDER_STATUS_VALUES, name="order_status")
    agent_action = postgresql.ENUM(*AGENT_ACTION_VALUES, name="agent_action")
    operator_decision = postgresql.ENUM(*OPERATOR_DECISION_VALUES, name="operator_decision")
    order_status.create(op.get_bind(), checkfirst=False)
    agent_action.create(op.get_bind(), checkfirst=False)
    operator_decision.create(op.get_bind(), checkfirst=False)

    # ---- Reference data tables ---------------------------------------------
    op.create_table(
        "currencies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(3), nullable=False),
        sa.Column("iso_number", sa.String(3), nullable=False),
        sa.Column("symbol", sa.String(5), nullable=False),
        sa.Column("decimal_points", sa.Integer(), nullable=False, server_default="2"),
        *_timestamps(),
        sa.UniqueConstraint("code", name="uq_currencies_code"),
    )

    op.create_table(
        "formats",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("description", sa.String(200), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("code", name="uq_formats_code"),
    )

    op.create_table(
        "retailers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("code", name="uq_retailers_code"),
    )

    op.create_table(
        "suppliers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=True),
        sa.Column("tax_id", sa.String(50), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("code", name="uq_suppliers_code"),
    )

    # ---- Documents ----------------------------------------------------------
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("format_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("code", name="uq_documents_code"),
        sa.ForeignKeyConstraint(
            ["format_id"], ["formats.id"], name="fk_documents_format_id", ondelete="RESTRICT"
        ),
    )

    # ---- Orders + line items -----------------------------------------------
    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("retailer_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("order_number", sa.String(100), nullable=False),
        sa.Column("order_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expected_delivery_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(*ORDER_STATUS_VALUES, name="order_status", create_type=False),
            nullable=False,
            server_default="pending_review",
        ),
        sa.Column("total_amount", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("currency_id", sa.Uuid(), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("documents", postgresql.JSONB(), nullable=False, server_default="[]"),
        *_timestamps(),
        sa.UniqueConstraint("code", name="uq_orders_code"),
        sa.ForeignKeyConstraint(
            ["retailer_id"], ["retailers.id"], name="fk_orders_retailer_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["suppliers.id"], name="fk_orders_supplier_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"], ["currencies.id"], name="fk_orders_currency_id", ondelete="RESTRICT"
        ),
    )
    op.create_index(
        "ix_orders_retailer_supplier", "orders", ["retailer_id", "supplier_id"]
    )

    op.create_table(
        "order_line_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("product_code", sa.String(100), nullable=False),
        sa.Column("product_name", sa.String(300), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.BigInteger(), nullable=False),
        sa.Column("line_total", sa.BigInteger(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("order_id", "line_number", name="uq_order_line_items_order_line"),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name="fk_order_line_items_order_id", ondelete="CASCADE"
        ),
    )

    # ---- Agent suggestions --------------------------------------------------
    op.create_table(
        "agent_suggestions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("agent_type", sa.String(20), nullable=False, server_default="analyst"),
        sa.Column(
            "action",
            postgresql.ENUM(*AGENT_ACTION_VALUES, name="agent_action", create_type=False),
            nullable=False,
        ),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("anomalies_detected", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("phoenix_trace_id", sa.String(200), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name="fk_agent_suggestions_order_id", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_agent_suggestions_order_id", "agent_suggestions", ["order_id"])

    # ---- Feedbacks ----------------------------------------------------------
    op.create_table(
        "feedbacks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("agent_suggestion_id", sa.Uuid(), nullable=False),
        sa.Column(
            "operator_decision",
            postgresql.ENUM(*OPERATOR_DECISION_VALUES, name="operator_decision", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "final_action",
            postgresql.ENUM(*AGENT_ACTION_VALUES, name="agent_action", create_type=False),
            nullable=False,
        ),
        sa.Column("operator_reason", sa.Text(), nullable=True),
        sa.Column("anomaly_feedback", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "phoenix_label_exported",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name="fk_feedbacks_order_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["agent_suggestion_id"],
            ["agent_suggestions.id"],
            name="fk_feedbacks_agent_suggestion_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_feedbacks_order_id", "feedbacks", ["order_id"])
    op.create_index("ix_feedbacks_agent_suggestion_id", "feedbacks", ["agent_suggestion_id"])


def downgrade() -> None:
    op.drop_index("ix_feedbacks_agent_suggestion_id", table_name="feedbacks")
    op.drop_index("ix_feedbacks_order_id", table_name="feedbacks")
    op.drop_table("feedbacks")

    op.drop_index("ix_agent_suggestions_order_id", table_name="agent_suggestions")
    op.drop_table("agent_suggestions")

    op.drop_table("order_line_items")
    op.drop_index("ix_orders_retailer_supplier", table_name="orders")
    op.drop_table("orders")

    op.drop_table("documents")
    op.drop_table("suppliers")
    op.drop_table("retailers")
    op.drop_table("formats")
    op.drop_table("currencies")

    bind = op.get_bind()
    postgresql.ENUM(name="operator_decision").drop(bind, checkfirst=False)
    postgresql.ENUM(name="agent_action").drop(bind, checkfirst=False)
    postgresql.ENUM(name="order_status").drop(bind, checkfirst=False)
