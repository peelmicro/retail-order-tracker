"""WebSocket integration tests — auth + receive event after order ingestion.

Uses FastAPI's sync TestClient because httpx async client doesn't have built-in
WebSocket support. Mixing sync + async transport in the same project is fine —
each test stands on its own.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.api.orders import get_dispatcher
from src.infrastructure.messaging.connection_manager import get_connection_manager
from src.infrastructure.parsers.dispatcher import default_dispatcher
from src.infrastructure.storage.minio_storage import get_file_storage
from src.main import app
from tests.helpers import InMemoryFileStorage

SAMPLES_DIR = Path(__file__).resolve().parents[3] / "samples" / "orders"


def _login_token(client: TestClient) -> str:
    response = client.post(
        "/auth/login",
        data={"username": "admin", "password": "admin123"},
    )
    return response.json()["accessToken"]


def test_websocket_without_token_is_rejected() -> None:
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/orders") as ws:
            ws.receive_json()
    assert exc_info.value.code == 4401


def test_websocket_with_invalid_token_is_rejected() -> None:
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/orders?token=not-a-real-jwt") as ws:
            ws.receive_json()
    assert exc_info.value.code == 4401


def test_websocket_receives_order_created_event_after_ingest() -> None:
    fake_storage = InMemoryFileStorage()
    # Reset the singleton so this test gets its own ConnectionManager
    get_connection_manager.cache_clear()
    app.dependency_overrides[get_file_storage] = lambda: fake_storage
    app.dependency_overrides[get_dispatcher] = lambda: default_dispatcher()

    try:
        with TestClient(app) as client:
            token = _login_token(client)
            sample = (SAMPLES_DIR / "sample-json.json").read_bytes()

            with client.websocket_connect(f"/ws/orders?token={token}") as ws:
                # Upload while connected
                response = client.post(
                    "/api/orders",
                    headers={"Authorization": f"Bearer {token}"},
                    files={"file": ("sample-json.json", sample, "application/json")},
                )
                assert response.status_code == 201
                expected_order_code = response.json()["orderCode"]

                event = ws.receive_json()
                assert event["eventType"] == "order.created"
                assert event["orderCode"] == expected_order_code
                assert event["retailerCode"] == "CARREFOUR-ES"
                assert event["totalAmount"] == 124_250
    finally:
        app.dependency_overrides.clear()
        get_connection_manager.cache_clear()
