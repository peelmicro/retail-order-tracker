"""EventBroadcaster adapter that fans out via the in-memory ConnectionManager."""

from src.application.dtos import CamelModel
from src.infrastructure.messaging.connection_manager import (
    ConnectionManager,
    get_connection_manager,
)


class InMemoryEventBroadcaster:
    def __init__(self, manager: ConnectionManager) -> None:
        self._manager = manager

    async def broadcast(self, event: CamelModel) -> None:
        await self._manager.broadcast(event.model_dump(mode="json", by_alias=True))


def get_event_broadcaster() -> InMemoryEventBroadcaster:
    return InMemoryEventBroadcaster(get_connection_manager())
