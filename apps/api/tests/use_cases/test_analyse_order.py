"""AnalyseOrderUseCase integration test against real DB with mocked agent."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import select

from src.application.ports.analyst_agent import AnalystAgentResult
from src.application.use_cases.analyse_order import (
    AnalyseOrderUseCase,
    OrderNotFoundError,
)
from src.domain.enums import AgentAction, OrderStatus
from src.infrastructure.persistence.engine import async_session_factory
from src.infrastructure.persistence.models.agent_suggestion import AgentSuggestion
from src.infrastructure.persistence.models.currency import Currency
from src.infrastructure.persistence.models.order import Order
from src.infrastructure.persistence.models.order_line_item import OrderLineItem
from src.infrastructure.persistence.models.retailer import Retailer
from src.infrastructure.persistence.models.supplier import Supplier


async def _seed_orders_for_pair(
    retailer_code: str,
    supplier_code: str,
    count: int,
    *,
    base_days_ago: int = 0,
) -> list[str]:
    """Insert `count` orders for the given retailer-supplier pair. Returns
    the list of order IDs as strings, newest first."""
    order_ids: list[str] = []
    async with async_session_factory() as session:
        retailer = Retailer(id=uuid4(), code=retailer_code, name=retailer_code)
        supplier = Supplier(id=uuid4(), code=supplier_code, name=supplier_code)
        currency = (
            await session.execute(select(Currency).where(Currency.code == "EUR"))
        ).scalar_one()
        session.add_all([retailer, supplier])
        await session.flush()

        now = datetime.now(UTC)
        for i in range(count):
            oid = uuid4()
            session.add(
                Order(
                    id=oid,
                    code=f"ORD-AN-{uuid4().hex[:6]}",
                    retailer_id=retailer.id,
                    supplier_id=supplier.id,
                    order_number=f"PO-AN-{i}",
                    order_date=now - timedelta(days=base_days_ago + i),
                    status=OrderStatus.APPROVED,
                    total_amount=1_000 + i * 500,
                    currency_id=currency.id,
                    raw_payload={"source_format": "test-seed"},
                    documents=[],
                )
            )
            session.add(
                OrderLineItem(
                    id=uuid4(),
                    order_id=oid,
                    line_number=1,
                    product_code=f"SKU-AN-{i}",
                    product_name=f"Product {i}",
                    quantity=10 + i,
                    unit_price=100,
                    line_total=(10 + i) * 100,
                )
            )
            order_ids.append(str(oid))
        await session.commit()
    return order_ids


def _agent_returning(action: AgentAction) -> MagicMock:
    agent = MagicMock()
    agent.analyze.return_value = AnalystAgentResult(
        action=action,
        confidence=0.88,
        reasoning="mocked",
        anomalies_detected=[],
        phoenix_trace_id="abc123",
    )
    return agent


@pytest.mark.asyncio
async def test_analyse_order_persists_suggestion_and_returns_result() -> None:
    marker = uuid4().hex[:8]
    order_ids = await _seed_orders_for_pair(
        retailer_code=f"R-AN-{marker}",
        supplier_code=f"S-AN-{marker}",
        count=3,
    )
    current_id = order_ids[0]  # target order = newest

    agent = _agent_returning(AgentAction.APPROVE)
    async with async_session_factory() as session:
        use_case = AnalyseOrderUseCase(session=session, agent=agent)
        from uuid import UUID

        result = await use_case.execute(UUID(current_id))

    assert result.action == AgentAction.APPROVE
    assert result.phoenix_trace_id == "abc123"
    # History excludes the current order → 2 recent orders considered
    assert result.recent_orders_considered == 2

    # Suggestion row persisted with the mocked fields
    async with async_session_factory() as session:
        suggestion = (
            await session.execute(
                select(AgentSuggestion).where(AgentSuggestion.id == result.suggestion_id)
            )
        ).scalar_one()
        assert suggestion.action == AgentAction.APPROVE
        assert suggestion.phoenix_trace_id == "abc123"
        assert float(suggestion.confidence) == 0.88

    # Agent was called with the right input shape
    agent.analyze.assert_called_once()
    arg = agent.analyze.call_args.args[0]
    assert arg.order.order_number == "PO-AN-0"  # newest (base_days_ago=0, i=0)
    assert len(arg.recent_orders) == 2
    # Recent orders ordered by order_date DESC, excluding current
    assert [o.order_number for o in arg.recent_orders] == ["PO-AN-1", "PO-AN-2"]


@pytest.mark.asyncio
async def test_analyse_order_unknown_id_raises() -> None:
    async with async_session_factory() as session:
        use_case = AnalyseOrderUseCase(session=session, agent=_agent_returning(AgentAction.APPROVE))
        with pytest.raises(OrderNotFoundError):
            await use_case.execute(uuid4())


@pytest.mark.asyncio
async def test_analyse_order_respects_recent_limit() -> None:
    marker = uuid4().hex[:8]
    order_ids = await _seed_orders_for_pair(
        retailer_code=f"R-LIM-{marker}",
        supplier_code=f"S-LIM-{marker}",
        count=10,
    )
    current_id = order_ids[0]

    agent = _agent_returning(AgentAction.APPROVE)
    async with async_session_factory() as session:
        use_case = AnalyseOrderUseCase(session=session, agent=agent)
        from uuid import UUID

        result = await use_case.execute(UUID(current_id), recent_limit=3)

    # 10 orders seeded, excluding current = 9 eligible, limit=3 → 3 considered
    assert result.recent_orders_considered == 3
