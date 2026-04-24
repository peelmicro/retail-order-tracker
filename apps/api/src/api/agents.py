"""Agents HTTP API — exposes the Analyst Agent to n8n and the frontend."""

from functools import lru_cache
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.application.dtos import CamelModel, OrderDTO
from src.application.ports.analyst_agent import (
    AnalystAgent,
    AnalystAgentInput,
    AnalystAgentResult,
)
from src.application.use_cases.analyse_order import (
    AnalyseOrderUseCase,
    OrderNotFoundError,
)
from src.domain.enums import AgentAction
from src.domain.user import User
from src.infrastructure.agents.errors import ApiKeyMissingError
from src.infrastructure.persistence.engine import get_session

router = APIRouter(prefix="/api/agents", tags=["agents"])


class AnalystRunRequest(CamelModel):
    order: OrderDTO
    recent_orders: list[OrderDTO] = Field(default_factory=list)


@lru_cache(maxsize=1)
def _analyst_agent_singleton() -> AnalystAgent:
    """Built lazily on first request so test code can override the dependency
    before the real ClaudeAnalystAgent ever gets constructed."""
    from src.infrastructure.agents.analyst_agent import ClaudeAnalystAgent

    return ClaudeAnalystAgent()


def get_analyst_agent() -> AnalystAgent:
    return _analyst_agent_singleton()


class AnalyseByOrderResponse(CamelModel):
    suggestion_id: UUID
    order_id: UUID
    action: AgentAction
    confidence: float
    reasoning: str
    anomalies_detected: list[str]
    phoenix_trace_id: str | None = None
    recent_orders_considered: int


@router.post("/analyst/run", response_model=AnalystAgentResult)
async def run_analyst(
    request: AnalystRunRequest,
    current_user: User = Depends(get_current_user),
    agent: AnalystAgent = Depends(get_analyst_agent),
) -> AnalystAgentResult:
    try:
        return agent.analyze(
            AnalystAgentInput(
                order=request.order,
                recent_orders=request.recent_orders,
            )
        )
    except ApiKeyMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analyst Agent failed: {exc}",
        ) from exc


@router.post(
    "/analyst/run/by-order/{order_id}",
    response_model=AnalyseByOrderResponse,
)
async def run_analyst_by_order(
    order_id: UUID,
    recent_limit: int = Query(default=50, ge=0, le=200),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    agent: AnalystAgent = Depends(get_analyst_agent),
) -> AnalyseByOrderResponse:
    """Analyse a persisted order and save the resulting suggestion.

    This is what n8n's "new-order" workflow triggers with just the order ID."""
    use_case = AnalyseOrderUseCase(session=session, agent=agent)
    try:
        result = await use_case.execute(order_id, recent_limit=recent_limit)
    except OrderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ApiKeyMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return AnalyseByOrderResponse(
        suggestion_id=result.suggestion_id,
        order_id=result.order_id,
        action=result.action,
        confidence=result.confidence,
        reasoning=result.reasoning,
        anomalies_detected=result.anomalies_detected,
        phoenix_trace_id=result.phoenix_trace_id,
        recent_orders_considered=result.recent_orders_considered,
    )
