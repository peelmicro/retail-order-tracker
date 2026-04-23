from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.enums import AgentAction
from src.infrastructure.persistence.base import Base, TimestampMixin
from src.infrastructure.persistence.models.order import Order


class AgentSuggestion(Base, TimestampMixin):
    __tablename__ = "agent_suggestions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    agent_type: Mapped[str] = mapped_column(String(20), nullable=False, default="analyst")
    action: Mapped[AgentAction] = mapped_column(
        ENUM(AgentAction, name="agent_action", create_type=False),
        nullable=False,
    )
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    anomalies_detected: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    phoenix_trace_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    order: Mapped[Order] = relationship()
