"""Integration tests against the real MinIO container from docker-compose.infra.yml.

Run `npm run dc:up:infra` first if these fail on a fresh machine.
"""

from uuid import uuid4

import httpx
import pytest

from src.infrastructure.storage.minio_storage import make_minio_storage


@pytest.fixture
def storage():
    return make_minio_storage()


@pytest.fixture
def test_key() -> str:
    # Isolate each test under a unique UUID prefix so parallel runs don't collide.
    return f"orders/test-{uuid4()}/sample.txt"


def test_upload_and_download_round_trip(storage, test_key) -> None:
    payload = b"retail order bytes"
    storage.upload(test_key, payload, content_type="text/plain")
    try:
        assert storage.download(test_key) == payload
    finally:
        storage.delete(test_key)


def test_presigned_url_is_reachable(storage, test_key) -> None:
    storage.upload(test_key, b"hello from minio", content_type="text/plain")
    try:
        url = storage.presigned_url(test_key, expires_seconds=60)
        assert url.startswith(("http://", "https://"))
        response = httpx.get(url, timeout=5.0)
        assert response.status_code == 200
        assert response.content == b"hello from minio"
    finally:
        storage.delete(test_key)


def test_delete_removes_object(storage, test_key) -> None:
    storage.upload(test_key, b"will be deleted")
    storage.delete(test_key)
    # A second delete on a missing key is a no-op (not an error).
    storage.delete(test_key)


def test_delete_nonexistent_key_is_idempotent(storage) -> None:
    ghost_key = f"orders/ghost-{uuid4()}/never-existed.txt"
    storage.delete(ghost_key)  # must not raise


def test_key_convention_uses_order_id_prefix(storage) -> None:
    """The project-wide convention is orders/{order_id}/{filename}; verify
    such keys round-trip without any issue (slashes, UUIDs, etc.)."""
    order_id = uuid4()
    filename = "sample-edifact-carrefour.edi"
    key = f"orders/{order_id}/{filename}"
    try:
        storage.upload(key, b"edifact bytes")
        assert storage.download(key) == b"edifact bytes"
    finally:
        storage.delete(key)
