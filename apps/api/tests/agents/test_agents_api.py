"""API tests for POST /api/agents/analyst/run.

The agent dependency is overridden so no real LLM is called.
"""

from unittest.mock import MagicMock

import httpx
import pytest

from src.api.agents import get_analyst_agent
from src.application.ports.analyst_agent import AnalystAgentResult
from src.domain.enums import AgentAction
from src.main import app


def _valid_order_payload() -> dict:
    return {
        "orderNumber": "PO-API-TEST-001",
        "orderDate": "2026-04-23T10:00:00Z",
        "retailerCode": "TEST-R",
        "retailerName": "Test Retailer",
        "supplierCode": "TEST-S",
        "supplierName": "Test Supplier",
        "currencyCode": "EUR",
        "totalAmount": 10_000,
        "lineItems": [
            {
                "lineNumber": 1,
                "productCode": "X",
                "quantity": 1,
                "unitPrice": 10_000,
                "lineTotal": 10_000,
            }
        ],
    }


@pytest.fixture
def mock_agent():
    m = MagicMock()
    m.analyze.return_value = AnalystAgentResult(
        action=AgentAction.APPROVE,
        confidence=0.9,
        reasoning="Looks normal",
        anomalies_detected=[],
        phoenix_trace_id="abc123",
    )
    return m


@pytest.fixture
async def client(mock_agent) -> httpx.AsyncClient:
    app.dependency_overrides[get_analyst_agent] = lambda: mock_agent
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


@pytest.mark.asyncio
async def test_unauthenticated_request_returns_401(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/agents/analyst/run",
        json={"order": _valid_order_payload(), "recentOrders": []},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_authenticated_request_returns_agent_result(
    client: httpx.AsyncClient, mock_agent
) -> None:
    token = await _login(client)

    response = await client.post(
        "/api/agents/analyst/run",
        headers={"Authorization": f"Bearer {token}"},
        json={"order": _valid_order_payload(), "recentOrders": []},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "approve"
    assert body["confidence"] == 0.9
    assert body["reasoning"] == "Looks normal"
    assert body["anomaliesDetected"] == []
    assert body["phoenixTraceId"] == "abc123"

    mock_agent.analyze.assert_called_once()
    passed_input = mock_agent.analyze.call_args.args[0]
    assert passed_input.order.order_number == "PO-API-TEST-001"
    assert passed_input.recent_orders == []


@pytest.mark.asyncio
async def test_invalid_payload_returns_422(client: httpx.AsyncClient) -> None:
    token = await _login(client)
    response = await client.post(
        "/api/agents/analyst/run",
        headers={"Authorization": f"Bearer {token}"},
        json={"order": {"orderNumber": "missing-other-fields"}, "recentOrders": []},
    )
    assert response.status_code == 422


# ---- POST /api/agents/analyst/run/by-order/{order_id} -------------------


@pytest.mark.asyncio
async def test_analyse_by_order_unauthenticated_returns_401(
    client: httpx.AsyncClient,
) -> None:
    from uuid import uuid4

    response = await client.post(f"/api/agents/analyst/run/by-order/{uuid4()}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_analyse_by_order_unknown_id_returns_404(
    client: httpx.AsyncClient,
) -> None:
    from uuid import uuid4

    token = await _login(client)
    response = await client.post(
        f"/api/agents/analyst/run/by-order/{uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_analyse_by_order_persists_suggestion_and_returns_result(
    client: httpx.AsyncClient, mock_agent
) -> None:
    """Seed a real order + pair history, call the endpoint with the order ID,
    assert the response echoes the (mocked) agent result and a suggestion row
    was written."""
    from datetime import UTC, datetime
    from uuid import UUID, uuid4

    from sqlalchemy import select

    from src.infrastructure.persistence.engine import async_session_factory
    from src.infrastructure.persistence.models.agent_suggestion import AgentSuggestion
    from src.infrastructure.persistence.models.currency import Currency
    from src.infrastructure.persistence.models.order import Order
    from src.infrastructure.persistence.models.order_line_item import OrderLineItem
    from src.infrastructure.persistence.models.retailer import Retailer
    from src.infrastructure.persistence.models.supplier import Supplier

    marker = uuid4().hex[:8]
    async with async_session_factory() as session:
        retailer = Retailer(id=uuid4(), code=f"R-BY-{marker}", name="By-Order Retailer")
        supplier = Supplier(id=uuid4(), code=f"S-BY-{marker}", name="By-Order Supplier")
        currency = (
            await session.execute(select(Currency).where(Currency.code == "EUR"))
        ).scalar_one()
        session.add_all([retailer, supplier])
        await session.flush()
        order_id = uuid4()
        order = Order(
            id=order_id,
            code=f"ORD-BY-{marker}",
            retailer_id=retailer.id,
            supplier_id=supplier.id,
            order_number="PO-BY-API",
            order_date=datetime.now(UTC),
            status="pending_review",
            total_amount=5_000,
            currency_id=currency.id,
            raw_payload={"source_format": "test"},
            documents=[],
        )
        session.add(order)
        # OrderDTO requires at least 1 line item — seed one so the use case
        # can reconstruct a valid OrderDTO from ORM rows.
        session.add(
            OrderLineItem(
                id=uuid4(),
                order_id=order_id,
                line_number=1,
                product_code="SKU-BY-API",
                product_name="By-order test product",
                quantity=5,
                unit_price=1_000,
                line_total=5_000,
            )
        )
        await session.commit()

    token = await _login(client)
    response = await client.post(
        f"/api/agents/analyst/run/by-order/{order_id}?recent_limit=10",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "approve"
    assert body["confidence"] == 0.9
    assert body["phoenixTraceId"] == "abc123"
    assert body["recentOrdersConsidered"] == 0  # no history for this fresh pair

    # Verify a suggestion row exists for this order
    async with async_session_factory() as session:
        suggestion = (
            await session.execute(
                select(AgentSuggestion).where(
                    AgentSuggestion.id == UUID(body["suggestionId"])
                )
            )
        ).scalar_one()
        assert suggestion.order_id == order_id
        assert suggestion.phoenix_trace_id == "abc123"
