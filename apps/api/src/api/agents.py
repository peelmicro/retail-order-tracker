"""Agents HTTP API — exposes the Analyst Agent to n8n and the frontend."""

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field

from src.api.deps import get_current_user
from src.application.dtos import CamelModel, OrderDTO
from src.application.ports.analyst_agent import (
    AnalystAgent,
    AnalystAgentInput,
    AnalystAgentResult,
)
from src.domain.user import User
from src.infrastructure.agents.errors import ApiKeyMissingError

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
