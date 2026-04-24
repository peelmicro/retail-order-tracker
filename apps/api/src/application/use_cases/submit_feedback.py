"""Submit operator feedback on an agent suggestion.

Side effects (in order):
  1. Verify the order exists and has at least one agent suggestion.
  2. Insert a feedback row tied to the latest suggestion.
  3. Update order.status based on the operator's final_action.
  4. Commit.
  5. Best-effort broadcast of the order.status_changed event.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.ports.event_broadcaster import (
    EventBroadcaster,
    OrderStatusChangedEvent,
)
from src.domain.enums import AgentAction, OperatorDecision, OrderStatus
from src.infrastructure.persistence.models.agent_suggestion import AgentSuggestion
from src.infrastructure.persistence.models.feedback import Feedback
from src.infrastructure.persistence.models.order import Order

_log = logging.getLogger(__name__)


_ACTION_TO_STATUS: dict[AgentAction, OrderStatus] = {
    AgentAction.APPROVE: OrderStatus.APPROVED,
    AgentAction.REQUEST_CLARIFICATION: OrderStatus.CLARIFICATION_REQUESTED,
    AgentAction.ESCALATE: OrderStatus.ESCALATED,
}


class OrderNotFoundError(Exception):
    def __init__(self, order_id: UUID) -> None:
        self.order_id = order_id
        super().__init__(f"Order {order_id} not found")


class NoAgentSuggestionError(Exception):
    def __init__(self, order_id: UUID) -> None:
        self.order_id = order_id
        super().__init__(f"Order {order_id} has no agent suggestion to give feedback on")


@dataclass(frozen=True)
class SubmitFeedbackInput:
    order_id: UUID
    operator_decision: OperatorDecision
    final_action: AgentAction
    operator_reason: str | None = None
    anomaly_feedback: dict | None = None


@dataclass(frozen=True)
class SubmitFeedbackResult:
    feedback_id: UUID
    order_id: UUID
    new_status: OrderStatus
    old_status: OrderStatus


class SubmitFeedbackUseCase:
    def __init__(
        self,
        session: AsyncSession,
        broadcaster: EventBroadcaster | None = None,
    ) -> None:
        self._session = session
        self._broadcaster = broadcaster

    async def execute(self, input: SubmitFeedbackInput) -> SubmitFeedbackResult:
        order = (
            await self._session.execute(select(Order).where(Order.id == input.order_id))
        ).scalar_one_or_none()
        if order is None:
            raise OrderNotFoundError(input.order_id)

        suggestion = (
            await self._session.execute(
                select(AgentSuggestion)
                .where(AgentSuggestion.order_id == input.order_id)
                .order_by(AgentSuggestion.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if suggestion is None:
            raise NoAgentSuggestionError(input.order_id)

        old_status = order.status
        new_status = _ACTION_TO_STATUS[input.final_action]
        order.status = new_status

        feedback_id = uuid4()
        self._session.add(
            Feedback(
                id=feedback_id,
                order_id=order.id,
                agent_suggestion_id=suggestion.id,
                operator_decision=input.operator_decision,
                final_action=input.final_action,
                operator_reason=input.operator_reason,
                anomaly_feedback=input.anomaly_feedback or {},
                phoenix_label_exported=False,
            )
        )

        await self._session.commit()

        if self._broadcaster is not None:
            try:
                await self._broadcaster.broadcast(
                    OrderStatusChangedEvent(
                        order_id=order.id,
                        order_code=order.code,
                        old_status=old_status,
                        new_status=new_status,
                        final_action=input.final_action,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                _log.warning("Status-change broadcast failed: %s", exc)

        return SubmitFeedbackResult(
            feedback_id=feedback_id,
            order_id=order.id,
            new_status=new_status,
            old_status=old_status,
        )
