"""WebSocket endpoints — real-time order events for the operator UI."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jwt import InvalidTokenError

from src.domain.user import User
from src.infrastructure.auth.jwt_service import decode_token
from src.infrastructure.auth.user_store import user_store
from src.infrastructure.messaging.connection_manager import get_connection_manager

_log = logging.getLogger(__name__)

router = APIRouter(tags=["websockets"])

# WebSocket close codes >= 4000 are application-defined; 4401 mirrors
# the HTTP 401 unauthorized convention.
WS_UNAUTHORIZED = 4401


def _authenticate(token: str | None) -> User:
    if not token:
        raise InvalidTokenError("missing token")
    payload = decode_token(token)
    username = payload.get("sub")
    if not isinstance(username, str):
        raise InvalidTokenError("invalid subject claim")
    user = user_store.get_by_username(username)
    if user is None or not user.is_active:
        raise InvalidTokenError("user not found or disabled")
    return user


@router.websocket("/ws/orders")
async def orders_ws(
    websocket: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    try:
        _authenticate(token)
    except InvalidTokenError as exc:
        await websocket.close(code=WS_UNAUTHORIZED, reason=str(exc))
        return

    manager = get_connection_manager()
    await manager.connect(websocket)
    try:
        # Hold the connection open; clients can ignore us or send pings.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
