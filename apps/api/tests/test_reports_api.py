"""GET /api/reports/daily — pandas aggregates over a fixed date.

Inserts orders with a deterministic created_at (2099-01-01) so the assertions
are independent of whatever other tests' orders sit in the database.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from src.domain.enums import AgentAction, OperatorDecision, OrderStatus
from src.infrastructure.persistence.engine import async_session_factory
from src.infrastructure.persistence.models.agent_suggestion import AgentSuggestion
from src.infrastructure.persistence.models.currency import Currency
from src.infrastructure.persistence.models.feedback import Feedback
from src.infrastructure.persistence.models.order import Order
from src.infrastructure.persistence.models.retailer import Retailer
from src.infrastructure.persistence.models.supplier import Supplier
from src.main import app

REPORT_DATE = date(2099, 1, 1)
REPORT_DATETIME = datetime(2099, 1, 1, 12, 0, tzinfo=UTC)


async def _seed_known_dataset() -> None:
    """Insert 3 orders all dated 2099-01-01: 2 approved + 1 pending, 2 retailers,
    one suggestion per order, 1 feedback. Returns nothing — tests query by
    that date."""
    async with async_session_factory() as session:
        # Reuse or create retailers/suppliers
        retailer_a = Retailer(
            id=uuid4(), code=f"REPORT-RA-{uuid4().hex[:6]}", name="Report Retailer A"
        )
        retailer_b = Retailer(
            id=uuid4(), code=f"REPORT-RB-{uuid4().hex[:6]}", name="Report Retailer B"
        )
        supplier = Supplier(
            id=uuid4(), code=f"REPORT-S-{uuid4().hex[:6]}", name="Report Supplier"
        )
        currency = (
            await session.execute(select(Currency).where(Currency.code == "EUR"))
        ).scalar_one()

        session.add_all([retailer_a, retailer_b, supplier])
        await session.flush()

        # 2 orders for retailer A (one approved, one pending), 1 for retailer B
        orders = []
        for retailer, status_value, total in [
            (retailer_a, OrderStatus.APPROVED, 10_000),
            (retailer_a, OrderStatus.PENDING_REVIEW, 25_000),
            (retailer_b, OrderStatus.APPROVED, 50_000),
        ]:
            order = Order(
                id=uuid4(),
                code=f"ORD-RPT-{uuid4().hex[:6]}",
                retailer_id=retailer.id,
                supplier_id=supplier.id,
                order_number=f"PO-RPT-{uuid4().hex[:6]}",
                order_date=REPORT_DATETIME,
                status=status_value,
                total_amount=total,
                currency_id=currency.id,
                raw_payload={},
                documents=[],
                created_at=REPORT_DATETIME,
                updated_at=REPORT_DATETIME,
            )
            session.add(order)
            orders.append(order)

        # One suggestion per order: 2 approve, 1 escalate
        for order, action in zip(
            orders,
            [AgentAction.APPROVE, AgentAction.APPROVE, AgentAction.ESCALATE],
            strict=True,
        ):
            session.add(
                AgentSuggestion(
                    id=uuid4(),
                    order_id=order.id,
                    agent_type="analyst",
                    action=action,
                    confidence=Decimal("0.9"),
                    reasoning="report seed",
                    anomalies_detected=[],
                )
            )

        await session.flush()

        # 1 feedback on the first order
        sug = (
            await session.execute(
                select(AgentSuggestion).where(AgentSuggestion.order_id == orders[0].id)
            )
        ).scalar_one()
        session.add(
            Feedback(
                id=uuid4(),
                order_id=orders[0].id,
                agent_suggestion_id=sug.id,
                operator_decision=OperatorDecision.ACCEPTED,
                final_action=AgentAction.APPROVE,
                operator_reason="report seed",
                anomaly_feedback={},
                phoenix_label_exported=False,
            )
        )
        await session.commit()


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _login(c: httpx.AsyncClient) -> str:
    response = await c.post(
        "/auth/login",
        data={"username": "admin", "password": "admin123"},
    )
    return response.json()["accessToken"]


@pytest.mark.asyncio
async def test_daily_report_unauthenticated_returns_401(client) -> None:
    response = await client.get("/api/reports/daily")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_daily_report_returns_aggregates_for_seeded_date(client) -> None:
    await _seed_known_dataset()
    token = await _login(client)
    response = await client.get(
        f"/api/reports/daily?from_date={REPORT_DATE.isoformat()}"
        f"&to_date={REPORT_DATE.isoformat()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["totalOrders"] == 3
    # 10_000 + 25_000 + 50_000
    assert body["totalAmount"] == 85_000
    # 85_000 / 3 = 28_333 (int truncation)
    assert body["averageAmount"] == 28_333

    assert body["ordersByStatus"]["approved"] == 2
    assert body["ordersByStatus"]["pending_review"] == 1

    # Retailer A has 2 orders (10k + 25k = 35k), Retailer B has 1 (50k)
    by_retailer = body["ordersByRetailer"]
    assert len(by_retailer) == 2
    # Sorted by ordersCount desc → Retailer A first
    assert by_retailer[0]["ordersCount"] == 2
    assert by_retailer[0]["totalAmount"] == 35_000
    assert by_retailer[1]["ordersCount"] == 1
    assert by_retailer[1]["totalAmount"] == 50_000

    assert body["ordersByAgentAction"]["approve"] == 2
    assert body["ordersByAgentAction"]["escalate"] == 1
    assert body["suggestionsCount"] == 3
    assert body["feedbacksCount"] == 1


@pytest.mark.asyncio
async def test_daily_report_empty_range_returns_zero_counts(client) -> None:
    token = await _login(client)
    far_past = "1970-01-01"
    response = await client.get(
        f"/api/reports/daily?from_date={far_past}&to_date={far_past}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["totalOrders"] == 0
    assert body["totalAmount"] == 0
    assert body["averageAmount"] == 0
    assert body["ordersByStatus"] == {}
    assert body["ordersByRetailer"] == []
    assert body["ordersByAgentAction"] == {}
    assert body["suggestionsCount"] == 0
    assert body["feedbacksCount"] == 0
