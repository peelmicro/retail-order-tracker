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
