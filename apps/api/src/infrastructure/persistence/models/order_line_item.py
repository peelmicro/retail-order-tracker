from uuid import UUID, uuid4

from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.persistence.base import Base, TimestampMixin
from src.infrastructure.persistence.models.order import Order


class OrderLineItem(Base, TimestampMixin):
    __tablename__ = "order_line_items"
    __table_args__ = (
        UniqueConstraint("order_id", "line_number", name="uq_order_line_items_order_line"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )

    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_code: Mapped[str] = mapped_column(String(100), nullable=False)
    product_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    line_total: Mapped[int] = mapped_column(BigInteger, nullable=False)

    order: Mapped[Order] = relationship(back_populates="line_items")
