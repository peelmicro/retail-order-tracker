"""POST /api/feedback — operator decision on an agent suggestion."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.application.dtos import CamelModel
from src.application.ports.event_broadcaster import EventBroadcaster
from src.application.use_cases.submit_feedback import (
    NoAgentSuggestionError,
    OrderNotFoundError,
    SubmitFeedbackInput,
    SubmitFeedbackUseCase,
)
from src.domain.enums import AgentAction, OperatorDecision, OrderStatus
from src.domain.user import User
from src.infrastructure.messaging.in_memory_broadcaster import get_event_broadcaster
from src.infrastructure.persistence.engine import get_session

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class FeedbackRequest(CamelModel):
    order_id: UUID
    operator_decision: OperatorDecision
    final_action: AgentAction
    operator_reason: str | None = None
    anomaly_feedback: dict = Field(default_factory=dict)


class FeedbackSubmittedResponse(CamelModel):
    feedback_id: UUID
    order_id: UUID
    new_status: OrderStatus
    old_status: OrderStatus


@router.post("", response_model=FeedbackSubmittedResponse, status_code=201)
async def submit_feedback(
    request: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    broadcaster: EventBroadcaster = Depends(get_event_broadcaster),
) -> FeedbackSubmittedResponse:
    use_case = SubmitFeedbackUseCase(session=session, broadcaster=broadcaster)
    try:
        result = await use_case.execute(
            SubmitFeedbackInput(
                order_id=request.order_id,
                operator_decision=request.operator_decision,
                final_action=request.final_action,
                operator_reason=request.operator_reason,
                anomaly_feedback=request.anomaly_feedback,
            )
        )
    except OrderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except NoAgentSuggestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return FeedbackSubmittedResponse(
        feedback_id=result.feedback_id,
        order_id=result.order_id,
        new_status=result.new_status,
        old_status=result.old_status,
    )
