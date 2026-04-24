"""ConnectionManager logic — connect, disconnect, broadcast, dead-conn cleanup."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.messaging.connection_manager import ConnectionManager


def _fake_websocket() -> MagicMock:
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


@pytest.mark.asyncio
async def test_connect_calls_accept_and_registers() -> None:
    manager = ConnectionManager()
    ws = _fake_websocket()

    await manager.connect(ws)

    ws.accept.assert_awaited_once()
    assert manager.connection_count == 1


@pytest.mark.asyncio
async def test_disconnect_removes_websocket() -> None:
    manager = ConnectionManager()
    ws = _fake_websocket()
    await manager.connect(ws)
    manager.disconnect(ws)
    assert manager.connection_count == 0


@pytest.mark.asyncio
async def test_disconnect_unknown_websocket_is_noop() -> None:
    manager = ConnectionManager()
    manager.disconnect(_fake_websocket())  # must not raise


@pytest.mark.asyncio
async def test_broadcast_sends_to_all_active_connections() -> None:
    manager = ConnectionManager()
    ws1 = _fake_websocket()
    ws2 = _fake_websocket()
    await manager.connect(ws1)
    await manager.connect(ws2)

    payload = {"eventType": "order.created", "orderCode": "ORD-X"}
    await manager.broadcast(payload)

    ws1.send_json.assert_awaited_once_with(payload)
    ws2.send_json.assert_awaited_once_with(payload)


@pytest.mark.asyncio
async def test_broadcast_drops_dead_connections() -> None:
    manager = ConnectionManager()
    healthy = _fake_websocket()
    dead = _fake_websocket()
    dead.send_json = AsyncMock(side_effect=RuntimeError("connection closed"))
    await manager.connect(healthy)
    await manager.connect(dead)

    await manager.broadcast({"any": "payload"})

    # Dead connection removed; healthy survives.
    assert manager.connection_count == 1
