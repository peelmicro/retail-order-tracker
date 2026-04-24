"""GET /api/reports/daily — operations dashboard aggregates via pandas."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pandas as pd
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.application.dtos import CamelModel
from src.domain.user import User
from src.infrastructure.persistence.engine import get_session
from src.infrastructure.persistence.models.agent_suggestion import AgentSuggestion
from src.infrastructure.persistence.models.feedback import Feedback
from src.infrastructure.persistence.models.order import Order
from src.infrastructure.persistence.models.retailer import Retailer

router = APIRouter(prefix="/api/reports", tags=["reports"])


class RetailerCount(CamelModel):
    retailer_code: str
    retailer_name: str
    orders_count: int
    total_amount: int


class DailyReportResponse(CamelModel):
    from_date: date
    to_date: date
    total_orders: int
    total_amount: int
    average_amount: int
    orders_by_status: dict[str, int]
    orders_by_retailer: list[RetailerCount]
    orders_by_agent_action: dict[str, int]
    suggestions_count: int
    feedbacks_count: int


@router.get("/daily", response_model=DailyReportResponse)
async def daily_report(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DailyReportResponse:
    today = datetime.now(UTC).date()
    if from_date is None:
        from_date = today
    if to_date is None:
        to_date = today

    range_start = datetime.combine(from_date, datetime.min.time(), tzinfo=UTC)
    range_end = datetime.combine(
        to_date + timedelta(days=1), datetime.min.time(), tzinfo=UTC
    )

    # Order-level rows for pandas aggregates.
    order_rows = (
        await session.execute(
            select(Order, Retailer)
            .join(Retailer, Order.retailer_id == Retailer.id)
            .where(Order.created_at >= range_start, Order.created_at < range_end)
        )
    ).all()

    if not order_rows:
        return DailyReportResponse(
            from_date=from_date,
            to_date=to_date,
            total_orders=0,
            total_amount=0,
            average_amount=0,
            orders_by_status={},
            orders_by_retailer=[],
            orders_by_agent_action={},
            suggestions_count=0,
            feedbacks_count=0,
        )

    df = pd.DataFrame(
        {
            "order_id": [str(o.id) for o, _ in order_rows],
            "status": [o.status.value for o, _ in order_rows],
            "total_amount": [int(o.total_amount) for o, _ in order_rows],
            "retailer_code": [r.code for _, r in order_rows],
            "retailer_name": [r.name for _, r in order_rows],
        }
    )

    total_orders = int(len(df))
    total_amount = int(df["total_amount"].sum())
    average_amount = int(df["total_amount"].mean())

    orders_by_status = df["status"].value_counts().to_dict()
    orders_by_status = {str(k): int(v) for k, v in orders_by_status.items()}

    by_retailer_df = (
        df.groupby(["retailer_code", "retailer_name"], as_index=False)
        .agg(orders_count=("order_id", "count"), total_amount=("total_amount", "sum"))
        .sort_values("orders_count", ascending=False)
    )
    orders_by_retailer = [
        RetailerCount(
            retailer_code=row["retailer_code"],
            retailer_name=row["retailer_name"],
            orders_count=int(row["orders_count"]),
            total_amount=int(row["total_amount"]),
        )
        for _, row in by_retailer_df.iterrows()
    ]

    # Suggestions grouped by action — straight SQL is simpler than another DataFrame.
    suggestion_rows = (
        await session.execute(
            select(AgentSuggestion.action, func.count(AgentSuggestion.id))
            .join(Order, AgentSuggestion.order_id == Order.id)
            .where(Order.created_at >= range_start, Order.created_at < range_end)
            .group_by(AgentSuggestion.action)
        )
    ).all()
    orders_by_agent_action = {action.value: int(count) for action, count in suggestion_rows}
    suggestions_count = int(sum(orders_by_agent_action.values()))

    feedbacks_count = int(
        (
            await session.execute(
                select(func.count(Feedback.id))
                .join(Order, Feedback.order_id == Order.id)
                .where(Order.created_at >= range_start, Order.created_at < range_end)
            )
        ).scalar_one()
    )

    return DailyReportResponse(
        from_date=from_date,
        to_date=to_date,
        total_orders=total_orders,
        total_amount=total_amount,
        average_amount=average_amount,
        orders_by_status=orders_by_status,
        orders_by_retailer=orders_by_retailer,
        orders_by_agent_action=orders_by_agent_action,
        suggestions_count=suggestions_count,
        feedbacks_count=feedbacks_count,
    )
