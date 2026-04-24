from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.enums import OrderStatus
from src.infrastructure.persistence.base import Base, TimestampMixin
from src.infrastructure.persistence.models.currency import Currency
from src.infrastructure.persistence.models.retailer import Retailer
from src.infrastructure.persistence.models.supplier import Supplier

if TYPE_CHECKING:
    from src.infrastructure.persistence.models.order_line_item import OrderLineItem


class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_retailer_supplier", "retailer_id", "supplier_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    retailer_id: Mapped[UUID] = mapped_column(
        ForeignKey("retailers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    supplier_id: Mapped[UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
    )

    order_number: Mapped[str] = mapped_column(String(100), nullable=False)
    order_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expected_delivery_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    status: Mapped[OrderStatus] = mapped_column(
        ENUM(
            OrderStatus,
            name="order_status",
            create_type=False,
            values_callable=lambda enum_class: [e.value for e in enum_class],
        ),
        nullable=False,
        default=OrderStatus.PENDING_REVIEW,
    )

    total_amount: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency_id: Mapped[UUID] = mapped_column(
        ForeignKey("currencies.id", ondelete="RESTRICT"),
        nullable=False,
    )

    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    documents: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    retailer: Mapped[Retailer] = relationship()
    supplier: Mapped[Supplier] = relationship()
    currency: Mapped[Currency] = relationship()
    line_items: Mapped[list["OrderLineItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )
