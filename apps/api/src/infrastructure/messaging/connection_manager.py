"""WebSocket connection registry + fanout."""

from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import WebSocket

_log = logging.getLogger(__name__)


class ConnectionManager:
    """In-memory registry of active WebSocket connections.

    Single-instance only — production with multiple API replicas would need
    Redis pub/sub or NATS to fan out events across processes.
    """

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        """Best-effort fanout. Dead connections are quietly dropped."""
        dead: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_json(message)
            except Exception as exc:  # noqa: BLE001 — broadcast must not raise
                _log.debug("Dropping dead WebSocket: %s", exc)
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


@lru_cache(maxsize=1)
def get_connection_manager() -> ConnectionManager:
    """Process-wide singleton — same instance for the WS endpoint and the
    broadcaster injected into use cases."""
    return ConnectionManager()
