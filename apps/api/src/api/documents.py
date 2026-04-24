"""Documents HTTP API — metadata + presigned download URL."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.application.dtos import CamelModel
from src.application.ports.file_storage import FileStorage
from src.domain.user import User
from src.infrastructure.persistence.engine import get_session
from src.infrastructure.persistence.models.document import Document
from src.infrastructure.storage.minio_storage import get_file_storage

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


class DocumentResponse(CamelModel):
    id: UUID
    code: str
    filename: str
    storage_path: str
    presigned_url: str | None = None


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    storage: FileStorage = Depends(get_file_storage),
) -> DocumentResponse:
    document = (
        await session.execute(select(Document).where(Document.id == document_id))
    ).scalar_one_or_none()
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )

    presigned_url: str | None = None
    try:
        presigned_url = storage.presigned_url(document.storage_path)
    except Exception as exc:  # noqa: BLE001 — presigning is best-effort
        _log.warning("Could not presign %s: %s", document.storage_path, exc)

    return DocumentResponse(
        id=document.id,
        code=document.code,
        filename=document.filename,
        storage_path=document.storage_path,
        presigned_url=presigned_url,
    )
