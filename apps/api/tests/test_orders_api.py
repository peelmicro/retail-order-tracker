"""POST /api/orders integration tests.

Hit the full stack: real DB, real parser dispatcher, in-memory FileStorage
substituted via dependency override. JWT auth is exercised end-to-end.
"""

from pathlib import Path

import httpx
import pytest

from src.api.orders import get_dispatcher
from src.infrastructure.parsers.dispatcher import default_dispatcher
from src.infrastructure.storage.minio_storage import get_file_storage
from src.main import app
from tests.helpers import InMemoryFileStorage

SAMPLES_DIR = Path(__file__).resolve().parents[3] / "samples" / "orders"


@pytest.fixture
def fake_storage() -> InMemoryFileStorage:
    return InMemoryFileStorage()


@pytest.fixture
async def client(fake_storage):
    # Override storage so the API doesn't write to real MinIO during tests.
    # Override dispatcher so we don't try to build the PDF parser
    # (which would call init_phoenix and instantiate ChatAnthropic).
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


@pytest.mark.asyncio
async def test_unauthenticated_upload_returns_401(client) -> None:
    response = await client.post(
        "/api/orders",
        files={"file": ("sample.json", b"{}", "application/json")},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_authenticated_json_upload_returns_201(client, fake_storage) -> None:
    token = await _login(client)
    sample = (SAMPLES_DIR / "sample-json.json").read_bytes()

    response = await client.post(
        "/api/orders",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("sample-json.json", sample, "application/json")},
    )
    assert response.status_code == 201
    body = response.json()

    assert body["orderCode"].startswith("ORD-2026-")
    assert body["parsedOrder"]["orderNumber"] == "PO-CARREFOUR-000123"
    assert body["parsedOrder"]["totalAmount"] == 124_250
    assert body["storagePath"].startswith("orders/")
    assert body["storagePath"].endswith("/sample-json.json")
    assert body["presignedUrl"].startswith("http://test/")

    # Verify the file landed in our fake storage
    assert body["storagePath"] in fake_storage.store


@pytest.mark.asyncio
async def test_unsupported_extension_returns_415(client) -> None:
    token = await _login(client)
    response = await client.post(
        "/api/orders",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("order.txt", b"random bytes", "text/plain")},
    )
    assert response.status_code == 415


@pytest.mark.asyncio
async def test_list_orders_unauthenticated_returns_401(client) -> None:
    response = await client.get("/api/orders")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_orders_returns_paginated_results(client) -> None:
    token = await _login(client)
    sample = (SAMPLES_DIR / "sample-json.json").read_bytes()
    # Ingest 3 orders so the list has something
    for _ in range(3):
        await client.post(
            "/api/orders",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("sample-json.json", sample, "application/json")},
        )

    response = await client.get(
        "/api/orders?page=1&page_size=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["pageSize"] == 2
    assert len(body["items"]) == 2
    assert body["total"] >= 3
    # Newest-first ordering
    item = body["items"][0]
    assert item["orderNumber"] == "PO-CARREFOUR-000123"
    assert item["status"] == "pending_review"
    assert item["hasSuggestion"] is False
    assert item["hasFeedback"] is False


@pytest.mark.asyncio
async def test_list_orders_filters_by_status(client) -> None:
    token = await _login(client)
    response = await client.get(
        "/api/orders?status=approved&page_size=5",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    for item in body["items"]:
        assert item["status"] == "approved"


@pytest.mark.asyncio
async def test_get_order_detail_returns_full_payload(client, fake_storage) -> None:
    token = await _login(client)
    sample = (SAMPLES_DIR / "sample-json.json").read_bytes()
    upload = await client.post(
        "/api/orders",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("sample-json.json", sample, "application/json")},
    )
    order_id = upload.json()["orderId"]

    response = await client.get(
        f"/api/orders/{order_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == order_id
    assert body["orderNumber"] == "PO-CARREFOUR-000123"
    assert len(body["lineItems"]) == 2
    assert body["lineItems"][0]["productCode"] == "SKU-OIL-EVO-1L"
    assert body["suggestion"] is None
    assert body["feedback"] is None


@pytest.mark.asyncio
async def test_get_order_detail_unknown_id_returns_404(client) -> None:
    from uuid import uuid4

    token = await _login(client)
    response = await client.get(
        f"/api/orders/{uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
