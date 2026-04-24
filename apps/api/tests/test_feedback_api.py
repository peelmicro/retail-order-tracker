"""POST /api/feedback — full flow including status mutation visible via GET."""

from decimal import Decimal
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from src.api.orders import get_dispatcher
from src.domain.enums import AgentAction, OperatorDecision, OrderStatus
from src.infrastructure.parsers.dispatcher import default_dispatcher
from src.infrastructure.persistence.engine import async_session_factory
from src.infrastructure.persistence.models.agent_suggestion import AgentSuggestion
from src.infrastructure.persistence.models.currency import Currency
from src.infrastructure.persistence.models.order import Order
from src.infrastructure.persistence.models.retailer import Retailer
from src.infrastructure.persistence.models.supplier import Supplier
from src.infrastructure.storage.minio_storage import get_file_storage
from src.main import app
from tests.helpers import InMemoryFileStorage

SAMPLES_DIR = Path(__file__).resolve().parents[3] / "samples" / "orders"


@pytest.fixture
def fake_storage() -> InMemoryFileStorage:
    return InMemoryFileStorage()


@pytest.fixture
async def client(fake_storage):
    app.dependency_overrides[get_file_storage] = lambda: fake_storage
    app.dependency_overrides[get_dispatcher] = lambda: default_dispatcher()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _login(c: httpx.AsyncClient) -> str:
    response = await c.post(
        "/auth/login",
        data={"username": "admin", "password": "admin123"},
    )
    return response.json()["accessToken"]


async def _seed_order_with_suggestion() -> tuple[str, str]:
    """Insert one order + one suggestion. Returns (order_id, suggestion_id) as strings."""
    async with async_session_factory() as session:
        retailer = (
            await session.execute(select(Retailer).limit(1))
        ).scalar_one_or_none()
        if retailer is None:
            retailer = Retailer(id=uuid4(), code=f"R-{uuid4().hex[:6]}", name="Test")
            session.add(retailer)
        supplier = (
            await session.execute(select(Supplier).limit(1))
        ).scalar_one_or_none()
        if supplier is None:
            supplier = Supplier(id=uuid4(), code=f"S-{uuid4().hex[:6]}", name="Test")
            session.add(supplier)
        currency = (
            await session.execute(select(Currency).where(Currency.code == "EUR"))
        ).scalar_one()
        await session.flush()

        order = Order(
            id=uuid4(),
            code=f"ORD-API-FB-{uuid4().hex[:6]}",
            retailer_id=retailer.id,
            supplier_id=supplier.id,
            order_number=f"PO-API-FB-{uuid4().hex[:6]}",
            order_date=datetime.now(UTC),
            status=OrderStatus.PENDING_REVIEW,
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
            confidence=Decimal("0.9"),
            reasoning="seed",
            anomalies_detected=[],
        )
        session.add(suggestion)
        await session.commit()
        return str(order.id), str(suggestion.id)


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(client) -> None:
    response = await client.post(
        "/api/feedback",
        json={
            "orderId": str(uuid4()),
            "operatorDecision": "accepted",
            "finalAction": "approve",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_submit_feedback_updates_order_status(client) -> None:
    order_id, _ = await _seed_order_with_suggestion()
    token = await _login(client)

    response = await client.post(
        "/api/feedback",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "orderId": order_id,
            "operatorDecision": "accepted",
            "finalAction": "approve",
            "operatorReason": "LGTM via API",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["newStatus"] == "approved"
    assert body["oldStatus"] == "pending_review"

    # Verify via GET /api/orders/{id} the new status is reflected
    detail = await client.get(
        f"/api/orders/{order_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail.status_code == 200
    assert detail.json()["status"] == "approved"
    assert detail.json()["feedback"]["operatorDecision"] == "accepted"


@pytest.mark.asyncio
async def test_submit_feedback_for_nonexistent_order_returns_404(client) -> None:
    token = await _login(client)
    response = await client.post(
        "/api/feedback",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "orderId": str(uuid4()),
            "operatorDecision": "accepted",
            "finalAction": "approve",
        },
    )
    assert response.status_code == 404
