"""POST /api/datasets/export — admin-only Phoenix dataset export."""

import httpx
import pytest

from src.main import app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _login(c: httpx.AsyncClient, username: str, password: str) -> str:
    response = await c.post(
        "/auth/login",
        data={"username": username, "password": password},
    )
    return response.json()["accessToken"]


@pytest.mark.asyncio
async def test_export_unauthenticated_returns_401(client) -> None:
    response = await client.post("/api/datasets/export")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_export_as_operator_returns_403(client) -> None:
    token = await _login(client, "operator", "operator123")
    response = await client.post(
        "/api/datasets/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_export_as_admin_returns_dataset(client) -> None:
    token = await _login(client, "admin", "admin123")
    response = await client.post(
        "/api/datasets/export?limit=50&confidence_threshold=0.9",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()

    assert "exportedAt" in body
    assert body["parserExamplesCount"] == 0
    assert body["analystExamplesCount"] >= 0

    dataset = body["dataset"]
    assert "parserAgent" in dataset
    assert "analystAgent" in dataset
    assert dataset["confidenceThreshold"] == 0.9

    # Aggregate shape sanity
    agg = dataset["analystAgent"]["aggregate"]
    assert "totalExamples" in agg
    assert "decisionAlignment" in agg
    assert "highConfidenceOverrides" in agg
