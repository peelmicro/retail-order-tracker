from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Text, Uuid
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.enums import AgentAction, OperatorDecision
from src.infrastructure.persistence.base import Base, TimestampMixin
from src.infrastructure.persistence.models.agent_suggestion import AgentSuggestion
from src.infrastructure.persistence.models.order import Order


class Feedback(Base, TimestampMixin):
    __tablename__ = "feedbacks"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_suggestion_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_suggestions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    operator_decision: Mapped[OperatorDecision] = mapped_column(
        ENUM(OperatorDecision, name="operator_decision", create_type=False),
        nullable=False,
    )
    final_action: Mapped[AgentAction] = mapped_column(
        ENUM(AgentAction, name="agent_action", create_type=False),
        nullable=False,
    )
    operator_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    anomaly_feedback: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    phoenix_label_exported: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    order: Mapped[Order] = relationship()
    agent_suggestion: Mapped[AgentSuggestion] = relationship()
