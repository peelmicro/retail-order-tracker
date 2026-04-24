"""GET /api/documents/{id} — metadata + presigned URL."""

from pathlib import Path
from uuid import uuid4

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
async def test_unauthenticated_returns_401(client) -> None:
    response = await client.get(f"/api/documents/{uuid4()}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unknown_document_returns_404(client) -> None:
    token = await _login(client)
    response = await client.get(
        f"/api/documents/{uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_returns_document_with_presigned_url(client) -> None:
    """Ingest an order (which creates a document row + uploads to storage),
    then fetch the document by id."""
    token = await _login(client)
    sample = (SAMPLES_DIR / "sample-json.json").read_bytes()
    upload = await client.post(
        "/api/orders",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("sample-json.json", sample, "application/json")},
    )
    assert upload.status_code == 201
    document_id = upload.json()["documentId"]

    response = await client.get(
        f"/api/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == document_id
    assert body["filename"] == "sample-json.json"
    assert body["storagePath"].startswith("orders/")
    # With the in-memory FileStorage fake, presigned URLs look like http://test/<key>
    assert body["presignedUrl"] is not None
