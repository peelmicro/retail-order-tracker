"""Admin-only operational data seed."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_admin
from src.api.orders import get_dispatcher
from src.application.dtos import CamelModel
from src.application.ports.file_storage import FileStorage
from src.application.use_cases.seed import SeedUseCase
from src.config import settings
from src.domain.user import User
from src.infrastructure.parsers.dispatcher import OrderParserDispatcher
from src.infrastructure.persistence.engine import get_session
from src.infrastructure.storage.minio_storage import get_file_storage

router = APIRouter(prefix="/api/seed", tags=["seed"])


class SeedResponse(CamelModel):
    retailers_created: int
    suppliers_created: int
    samples_uploaded: int
    historical_orders_created: int
    pending_orders_created: int
    agent_suggestions_created: int
    feedbacks_created: int


@router.post("", response_model=SeedResponse)
async def seed(
    historical_count: int = Query(default=200, ge=0, le=10_000),
    pending_count: int = Query(default=30, ge=0, le=1_000),
    feedback_count: int = Query(default=50, ge=0, le=1_000),
    current_user: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
    storage: FileStorage = Depends(get_file_storage),
    dispatcher: OrderParserDispatcher = Depends(get_dispatcher),
) -> SeedResponse:
    use_case = SeedUseCase(
        session=session,
        storage=storage,
        dispatcher=dispatcher,
        samples_dir=settings.samples_orders_dir,
    )
    result = await use_case.execute(
        historical_count=historical_count,
        pending_count=pending_count,
        feedback_count=feedback_count,
    )
    return SeedResponse(
        retailers_created=result.retailers_created,
        suppliers_created=result.suppliers_created,
        samples_uploaded=result.samples_uploaded,
        historical_orders_created=result.historical_orders_created,
        pending_orders_created=result.pending_orders_created,
        agent_suggestions_created=result.agent_suggestions_created,
        feedbacks_created=result.feedbacks_created,
    )
