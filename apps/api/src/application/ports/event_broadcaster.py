"""Port for broadcasting domain events to subscribers (WebSocket clients)."""

from typing import Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import Field

from src.application.dtos import CamelModel
from src.domain.enums import AgentAction, OrderStatus


class OrderCreatedEvent(CamelModel):
    event_type: Literal["order.created"] = Field(default="order.created")
    order_id: UUID
    order_code: str
    retailer_code: str
    retailer_name: str
    supplier_code: str
    supplier_name: str
    currency_code: str
    total_amount: int


class OrderStatusChangedEvent(CamelModel):
    event_type: Literal["order.status_changed"] = Field(default="order.status_changed")
    order_id: UUID
    order_code: str
    old_status: OrderStatus
    new_status: OrderStatus
    final_action: AgentAction


@runtime_checkable
class EventBroadcaster(Protocol):
    async def broadcast(self, event: CamelModel) -> None: ...
