"""Orders HTTP API — multipart upload, parse, persist, list, detail."""

from __future__ import annotations

import logging
from datetime import datetime
from functools import lru_cache
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.application.dtos import CamelModel, OrderDTO
from src.application.exceptions import UnknownCurrencyError, UnknownFormatError
from src.application.ports.event_broadcaster import EventBroadcaster
from src.application.ports.file_storage import FileStorage
from src.application.ports.order_parser import UnsupportedFormatError
from src.application.use_cases.ingest_order import IngestOrderInput, IngestOrderUseCase
from src.domain.enums import AgentAction, OperatorDecision, OrderStatus
from src.domain.user import User
from src.infrastructure.messaging.in_memory_broadcaster import get_event_broadcaster
from src.infrastructure.parsers.dispatcher import OrderParserDispatcher, default_dispatcher
from src.infrastructure.persistence.engine import get_session
from src.infrastructure.persistence.models.agent_suggestion import AgentSuggestion
from src.infrastructure.persistence.models.currency import Currency
from src.infrastructure.persistence.models.feedback import Feedback
from src.infrastructure.persistence.models.order import Order
from src.infrastructure.persistence.models.order_line_item import OrderLineItem
from src.infrastructure.persistence.models.retailer import Retailer
from src.infrastructure.persistence.models.supplier import Supplier
from src.infrastructure.storage.minio_storage import get_file_storage

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orders", tags=["orders"])


class OrderIngestResponse(CamelModel):
    order_id: UUID
    order_code: str
    document_id: UUID
    storage_path: str
    parsed_order: OrderDTO
    presigned_url: str | None = Field(default=None)


class OrderSummaryResponse(CamelModel):
    id: UUID
    code: str
    order_number: str
    retailer_code: str
    retailer_name: str
    supplier_code: str
    supplier_name: str
    currency_code: str
    total_amount: int
    status: OrderStatus
    order_date: datetime
    expected_delivery_date: datetime | None = None
    has_suggestion: bool
    suggestion_action: AgentAction | None = None
    suggestion_confidence: float | None = None
    has_feedback: bool
    created_at: datetime


class OrderListResponse(CamelModel):
    items: list[OrderSummaryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class OrderLineItemResponse(CamelModel):
    line_number: int
    product_code: str
    product_name: str | None = None
    quantity: int
    unit_price: int
    line_total: int


class AgentSuggestionResponse(CamelModel):
    id: UUID
    agent_type: str
    action: AgentAction
    confidence: float
    reasoning: str
    anomalies_detected: list[str]
    phoenix_trace_id: str | None = None
    created_at: datetime


class FeedbackResponse(CamelModel):
    id: UUID
    operator_decision: OperatorDecision
    final_action: AgentAction
    operator_reason: str | None = None
    anomaly_feedback: dict
    created_at: datetime


class OrderDetailResponse(CamelModel):
    id: UUID
    code: str
    order_number: str
    retailer_code: str
    retailer_name: str
    supplier_code: str
    supplier_name: str
    currency_code: str
    total_amount: int
    status: OrderStatus
    order_date: datetime
    expected_delivery_date: datetime | None = None
    raw_payload: dict
    documents: list[str]
    line_items: list[OrderLineItemResponse]
    suggestion: AgentSuggestionResponse | None = None
    feedback: FeedbackResponse | None = None
    created_at: datetime
    updated_at: datetime


@lru_cache(maxsize=1)
def _dispatcher_singleton() -> OrderParserDispatcher:
    """Build the dispatcher once. Includes the PDF parser if an Anthropic
    key is set; falls back to the 4 deterministic parsers otherwise."""
    try:
        from src.infrastructure.agents.parser_agent import ClaudeParserAgent

        agent = ClaudeParserAgent()
        _log.info("Order dispatcher built with PDF support (Parser Agent)")
        return default_dispatcher(parser_agent=agent)
    except Exception as exc:  # noqa: BLE001 — graceful degradation
        _log.warning("PDF support disabled: %s", exc)
        return default_dispatcher()


def get_dispatcher() -> OrderParserDispatcher:
    return _dispatcher_singleton()


@router.post(
    "",
    response_model=OrderIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_order(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    storage: FileStorage = Depends(get_file_storage),
    dispatcher: OrderParserDispatcher = Depends(get_dispatcher),
    broadcaster: EventBroadcaster = Depends(get_event_broadcaster),
) -> OrderIngestResponse:
    file_bytes = await file.read()
    filename = file.filename or "uploaded.bin"

    use_case = IngestOrderUseCase(
        session=session,
        storage=storage,
        dispatcher=dispatcher,
        broadcaster=broadcaster,
    )

    try:
        result = await use_case.execute(
            IngestOrderInput(
                file_bytes=file_bytes,
                filename=filename,
                mime_type=file.content_type,
            )
        )
    except UnsupportedFormatError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except (UnknownCurrencyError, UnknownFormatError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    presigned_url: str | None = None
    try:
        presigned_url = storage.presigned_url(result.storage_path)
    except Exception as exc:  # noqa: BLE001 — presigning is best-effort
        _log.warning("Could not build presigned URL: %s", exc)

    return OrderIngestResponse(
        order_id=result.order_id,
        order_code=result.order_code,
        document_id=result.document_id,
        storage_path=result.storage_path,
        parsed_order=result.parsed_order,
        presigned_url=presigned_url,
    )


@router.get("", response_model=OrderListResponse)
async def list_orders(
    status_filter: OrderStatus | None = Query(default=None, alias="status"),
    retailer_code: str | None = Query(default=None),
    supplier_code: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrderListResponse:
    base = (
        select(Order, Retailer, Supplier, Currency)
        .join(Retailer, Order.retailer_id == Retailer.id)
        .join(Supplier, Order.supplier_id == Supplier.id)
        .join(Currency, Order.currency_id == Currency.id)
    )
    if status_filter is not None:
        base = base.where(Order.status == status_filter)
    if retailer_code is not None:
        base = base.where(Retailer.code == retailer_code)
    if supplier_code is not None:
        base = base.where(Supplier.code == supplier_code)

    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    rows = (
        await session.execute(
            base.order_by(Order.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    order_ids = [row[0].id for row in rows]
    suggestions_by_order = await _latest_suggestion_per_order(session, order_ids)
    feedbacks_by_order = await _feedback_per_order(session, order_ids)

    items: list[OrderSummaryResponse] = []
    for order, retailer, supplier, currency in rows:
        suggestion = suggestions_by_order.get(order.id)
        items.append(
            OrderSummaryResponse(
                id=order.id,
                code=order.code,
                order_number=order.order_number,
                retailer_code=retailer.code,
                retailer_name=retailer.name,
                supplier_code=supplier.code,
                supplier_name=supplier.name,
                currency_code=currency.code,
                total_amount=order.total_amount,
                status=order.status,
                order_date=order.order_date,
                expected_delivery_date=order.expected_delivery_date,
                has_suggestion=suggestion is not None,
                suggestion_action=suggestion.action if suggestion else None,
                suggestion_confidence=(
                    float(suggestion.confidence) if suggestion else None
                ),
                has_feedback=order.id in feedbacks_by_order,
                created_at=order.created_at,
            )
        )

    total_pages = (total + page_size - 1) // page_size if total else 0
    return OrderListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{order_id}", response_model=OrderDetailResponse)
async def get_order(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrderDetailResponse:
    row = (
        await session.execute(
            select(Order, Retailer, Supplier, Currency)
            .join(Retailer, Order.retailer_id == Retailer.id)
            .join(Supplier, Order.supplier_id == Supplier.id)
            .join(Currency, Order.currency_id == Currency.id)
            .where(Order.id == order_id)
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found",
        )
    order, retailer, supplier, currency = row

    line_item_rows = (
        await session.execute(
            select(OrderLineItem)
            .where(OrderLineItem.order_id == order_id)
            .order_by(OrderLineItem.line_number)
        )
    ).scalars().all()

    suggestion = (
        await session.execute(
            select(AgentSuggestion)
            .where(AgentSuggestion.order_id == order_id)
            .order_by(AgentSuggestion.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    feedback = (
        await session.execute(
            select(Feedback)
            .where(Feedback.order_id == order_id)
            .order_by(Feedback.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    return OrderDetailResponse(
        id=order.id,
        code=order.code,
        order_number=order.order_number,
        retailer_code=retailer.code,
        retailer_name=retailer.name,
        supplier_code=supplier.code,
        supplier_name=supplier.name,
        currency_code=currency.code,
        total_amount=order.total_amount,
        status=order.status,
        order_date=order.order_date,
        expected_delivery_date=order.expected_delivery_date,
        raw_payload=order.raw_payload,
        documents=order.documents,
        line_items=[
            OrderLineItemResponse(
                line_number=li.line_number,
                product_code=li.product_code,
                product_name=li.product_name,
                quantity=li.quantity,
                unit_price=li.unit_price,
                line_total=li.line_total,
            )
            for li in line_item_rows
        ],
        suggestion=(
            AgentSuggestionResponse(
                id=suggestion.id,
                agent_type=suggestion.agent_type,
                action=suggestion.action,
                confidence=float(suggestion.confidence),
                reasoning=suggestion.reasoning,
                anomalies_detected=suggestion.anomalies_detected,
                phoenix_trace_id=suggestion.phoenix_trace_id,
                created_at=suggestion.created_at,
            )
            if suggestion
            else None
        ),
        feedback=(
            FeedbackResponse(
                id=feedback.id,
                operator_decision=feedback.operator_decision,
                final_action=feedback.final_action,
                operator_reason=feedback.operator_reason,
                anomaly_feedback=feedback.anomaly_feedback,
                created_at=feedback.created_at,
            )
            if feedback
            else None
        ),
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


async def _latest_suggestion_per_order(
    session: AsyncSession, order_ids: list[UUID]
) -> dict[UUID, AgentSuggestion]:
    if not order_ids:
        return {}
    rows = (
        await session.execute(
            select(AgentSuggestion)
            .where(AgentSuggestion.order_id.in_(order_ids))
            .order_by(AgentSuggestion.order_id, AgentSuggestion.created_at.desc())
        )
    ).scalars().all()
    by_order: dict[UUID, AgentSuggestion] = {}
    for s in rows:
        by_order.setdefault(s.order_id, s)
    return by_order


async def _feedback_per_order(
    session: AsyncSession, order_ids: list[UUID]
) -> dict[UUID, Feedback]:
    if not order_ids:
        return {}
    rows = (
        await session.execute(
            select(Feedback)
            .where(Feedback.order_id.in_(order_ids))
            .order_by(Feedback.order_id, Feedback.created_at.desc())
        )
    ).scalars().all()
    by_order: dict[UUID, Feedback] = {}
    for f in rows:
        by_order.setdefault(f.order_id, f)
    return by_order
