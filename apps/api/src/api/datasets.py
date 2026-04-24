"""POST /api/datasets/export — admin-only Phoenix-compatible dataset export."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_admin
from src.application.dtos import CamelModel
from src.application.use_cases.export_dataset import ExportDatasetUseCase
from src.domain.user import User
from src.infrastructure.persistence.engine import get_session

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


class DatasetExportResponse(CamelModel):
    exported_at: str
    parser_examples_count: int
    analyst_examples_count: int
    marked_feedback_count: int
    dataset: dict


@router.post("/export", response_model=DatasetExportResponse)
async def export_dataset(
    limit: int = Query(default=100, ge=1, le=1000),
    confidence_threshold: float = Query(default=0.9, ge=0.0, le=1.0),
    current_user: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> DatasetExportResponse:
    use_case = ExportDatasetUseCase(
        session=session,
        confidence_threshold=confidence_threshold,
    )
    result = await use_case.execute(limit=limit)
    return DatasetExportResponse(
        exported_at=result.exported_at.isoformat(),
        parser_examples_count=result.parser_examples_count,
        analyst_examples_count=result.analyst_examples_count,
        marked_feedback_count=result.marked_feedback_count,
        dataset=result.dataset,
    )
