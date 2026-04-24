"""POST /api/seed — admin-only with parametrised counts."""

import httpx
import pytest

from src.api.orders import get_dispatcher
from src.infrastructure.parsers.dispatcher import default_dispatcher
from src.infrastructure.storage.minio_storage import get_file_storage
from src.main import app
from tests.helpers import InMemoryFileStorage


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


async def _login(c: httpx.AsyncClient, username: str, password: str) -> str:
    response = await c.post(
        "/auth/login",
        data={"username": username, "password": password},
    )
    return response.json()["accessToken"]


@pytest.mark.asyncio
async def test_seed_unauthenticated_returns_401(client) -> None:
    response = await client.post("/api/seed")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_seed_as_operator_returns_403(client) -> None:
    token = await _login(client, "operator", "operator123")
    response = await client.post(
        "/api/seed",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_seed_as_admin_returns_counts(client) -> None:
    """Query param names use the Python function argument names (snake_case),
    not Pydantic camelCase aliases — so the URL uses snake_case here. The
    response body still comes back in camelCase via the response_model alias."""
    token = await _login(client, "admin", "admin123")
    response = await client.post(
        "/api/seed?historical_count=3&pending_count=1&feedback_count=1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["historicalOrdersCreated"] == 3
    assert body["pendingOrdersCreated"] == 1
    assert body["feedbacksCreated"] == 1
    assert body["retailersCreated"] == 4
    assert body["suppliersCreated"] == 8
    assert body["samplesUploaded"] == 4
    assert body["agentSuggestionsCreated"] == 4
