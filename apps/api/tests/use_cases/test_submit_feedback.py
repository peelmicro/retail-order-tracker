"""SubmitFeedbackUseCase — uses real DB to verify status mutation."""

from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import select

from src.application.ports.event_broadcaster import OrderStatusChangedEvent
from src.application.use_cases.submit_feedback import (
    NoAgentSuggestionError,
    OrderNotFoundError,
    SubmitFeedbackInput,
    SubmitFeedbackUseCase,
)
from src.domain.enums import AgentAction, OperatorDecision, OrderStatus
from src.infrastructure.persistence.engine import async_session_factory
from src.infrastructure.persistence.models.agent_suggestion import AgentSuggestion
from src.infrastructure.persistence.models.currency import Currency
from src.infrastructure.persistence.models.feedback import Feedback
from src.infrastructure.persistence.models.order import Order
from src.infrastructure.persistence.models.retailer import Retailer
from src.infrastructure.persistence.models.supplier import Supplier


async def _seed_order_with_suggestion(
    *, status: OrderStatus = OrderStatus.PENDING_REVIEW
) -> tuple[Order, AgentSuggestion]:
    """Insert one order + one agent suggestion in a fresh session."""
    async with async_session_factory() as session:
        # Find any existing retailer/supplier/currency to attach to
        retailer = (
            await session.execute(select(Retailer).limit(1))
        ).scalar_one_or_none()
        if retailer is None:
            retailer = Retailer(id=uuid4(), code=f"R-{uuid4().hex[:6]}", name="Test Retailer")
            session.add(retailer)
        supplier = (
            await session.execute(select(Supplier).limit(1))
        ).scalar_one_or_none()
        if supplier is None:
            supplier = Supplier(id=uuid4(), code=f"S-{uuid4().hex[:6]}", name="Test Supplier")
            session.add(supplier)
        currency = (
            await session.execute(select(Currency).where(Currency.code == "EUR"))
        ).scalar_one()
        await session.flush()

        from datetime import UTC, datetime

        order = Order(
            id=uuid4(),
            code=f"ORD-FEEDBACK-{uuid4().hex[:6]}",
            retailer_id=retailer.id,
            supplier_id=supplier.id,
            order_number=f"PO-FEEDBACK-{uuid4().hex[:6]}",
            order_date=datetime.now(UTC),
            status=status,
            total_amount=10_000,
            currency_id=currency.id,
            raw_payload={},
            documents=[],
        )
        session.add(order)
        suggestion = AgentSuggestion(
            id=uuid4(),
            order_id=order.id,
            agent_type="analyst",
            action=AgentAction.APPROVE,
            confidence=Decimal("0.92"),
            reasoning="seeded for feedback test",
            anomalies_detected=[],
        )
        session.add(suggestion)
        await session.commit()
        return order, suggestion


@pytest.mark.asyncio
async def test_submits_feedback_and_updates_status_to_approved() -> None:
    order, _ = await _seed_order_with_suggestion()
    broadcaster = AsyncMock()
    broadcaster.broadcast = AsyncMock()

    async with async_session_factory() as session:
        use_case = SubmitFeedbackUseCase(session=session, broadcaster=broadcaster)
        result = await use_case.execute(
            SubmitFeedbackInput(
                order_id=order.id,
                operator_decision=OperatorDecision.ACCEPTED,
                final_action=AgentAction.APPROVE,
                operator_reason="LGTM",
            )
        )

    assert result.new_status == OrderStatus.APPROVED
    assert result.old_status == OrderStatus.PENDING_REVIEW

    # Verify the row was inserted and the order status mutated
    async with async_session_factory() as session:
        feedback = (
            await session.execute(select(Feedback).where(Feedback.id == result.feedback_id))
        ).scalar_one()
        assert feedback.operator_decision == OperatorDecision.ACCEPTED
        assert feedback.final_action == AgentAction.APPROVE

        order_after = (
            await session.execute(select(Order).where(Order.id == order.id))
        ).scalar_one()
        assert order_after.status == OrderStatus.APPROVED

    # Broadcaster must have been called with an OrderStatusChangedEvent
    broadcaster.broadcast.assert_awaited_once()
    arg = broadcaster.broadcast.await_args.args[0]
    assert isinstance(arg, OrderStatusChangedEvent)
    assert arg.new_status == OrderStatus.APPROVED


@pytest.mark.asyncio
async def test_submits_feedback_and_updates_status_to_escalated() -> None:
    order, _ = await _seed_order_with_suggestion()

    async with async_session_factory() as session:
        use_case = SubmitFeedbackUseCase(session=session)
        result = await use_case.execute(
            SubmitFeedbackInput(
                order_id=order.id,
                operator_decision=OperatorDecision.MODIFIED,
                final_action=AgentAction.ESCALATE,
            )
        )

    assert result.new_status == OrderStatus.ESCALATED


@pytest.mark.asyncio
async def test_unknown_order_raises_order_not_found() -> None:
    async with async_session_factory() as session:
        use_case = SubmitFeedbackUseCase(session=session)
        with pytest.raises(OrderNotFoundError):
            await use_case.execute(
                SubmitFeedbackInput(
                    order_id=uuid4(),
                    operator_decision=OperatorDecision.ACCEPTED,
                    final_action=AgentAction.APPROVE,
                )
            )


@pytest.mark.asyncio
async def test_order_without_suggestion_raises() -> None:
    """Insert an order with no AgentSuggestion. Submitting feedback must 400."""
    from datetime import UTC, datetime

    async with async_session_factory() as session:
        retailer = (
            await session.execute(select(Retailer).limit(1))
        ).scalar_one_or_none() or Retailer(
            id=uuid4(), code=f"R-{uuid4().hex[:6]}", name="Test"
        )
        supplier = (
            await session.execute(select(Supplier).limit(1))
        ).scalar_one_or_none() or Supplier(
            id=uuid4(), code=f"S-{uuid4().hex[:6]}", name="Test"
        )
        currency = (
            await session.execute(select(Currency).where(Currency.code == "EUR"))
        ).scalar_one()
        if not retailer.id:
            session.add(retailer)
        if not supplier.id:
            session.add(supplier)
        await session.flush()

        order = Order(
            id=uuid4(),
            code=f"ORD-NO-SUG-{uuid4().hex[:6]}",
            retailer_id=retailer.id,
            supplier_id=supplier.id,
            order_number="PO-NO-SUG",
            order_date=datetime.now(UTC),
            status=OrderStatus.PENDING_REVIEW,
            total_amount=100,
            currency_id=currency.id,
            raw_payload={},
            documents=[],
        )
        session.add(order)
        await session.commit()
        order_id = order.id

    async with async_session_factory() as session:
        use_case = SubmitFeedbackUseCase(session=session)
        with pytest.raises(NoAgentSuggestionError):
            await use_case.execute(
                SubmitFeedbackInput(
                    order_id=order_id,
                    operator_decision=OperatorDecision.ACCEPTED,
                    final_action=AgentAction.APPROVE,
                )
            )
