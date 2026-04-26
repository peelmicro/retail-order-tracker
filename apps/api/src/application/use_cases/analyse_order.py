"""Run the Analyst Agent against a persisted order and save the suggestion.

This is the production flow (called by n8n's "new-order" workflow):

  1. Fetch the order from DB, reconstruct OrderDTO from columns + line items
     (not from raw_payload, because seed-generated orders store a placeholder).
  2. Fetch up to `recent_limit` orders for the same retailer-supplier pair,
     ordered by order_date DESC, excluding the current order.
  3. Invoke the AnalystAgent with the current + recent OrderDTOs.
  4. Persist an AgentSuggestion row carrying the result + phoenix_trace_id.

Contrast with the stateless `POST /api/agents/analyst/run` endpoint that
receives a raw OrderDTO in the body and doesn't write anything to the DB.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos import OrderDTO, OrderLineItemDTO
from src.application.ports.analyst_agent import AnalystAgent, AnalystAgentInput
from src.domain.enums import AgentAction
from src.infrastructure.persistence.models.agent_suggestion import AgentSuggestion
from src.infrastructure.persistence.models.currency import Currency
from src.infrastructure.persistence.models.order import Order
from src.infrastructure.persistence.models.order_line_item import OrderLineItem
from src.infrastructure.persistence.models.retailer import Retailer
from src.infrastructure.persistence.models.supplier import Supplier

_log = logging.getLogger(__name__)


class OrderNotFoundError(Exception):
    def __init__(self, order_id: UUID) -> None:
        self.order_id = order_id
        super().__init__(f"Order {order_id} not found")


@dataclass(frozen=True)
class AnalyseOrderResult:
    suggestion_id: UUID
    order_id: UUID
    action: AgentAction
    confidence: float
    reasoning: str
    anomalies_detected: list[str]
    phoenix_trace_id: str | None
    recent_orders_considered: int


class AnalyseOrderUseCase:
    def __init__(self, session: AsyncSession, agent: AnalystAgent) -> None:
        self._session = session
        self._agent = agent

    async def execute(
        self,
        order_id: UUID,
        *,
        recent_limit: int = 50,
    ) -> AnalyseOrderResult:
        order = (
            await self._session.execute(select(Order).where(Order.id == order_id))
        ).scalar_one_or_none()
        if order is None:
            raise OrderNotFoundError(order_id)

        current_dto = await self._build_order_dto(order)

        # Pull a few extra candidates so we can still hit recent_limit after
        # dropping orders that are missing line items (which can't satisfy the
        # OrderDTO's min_length=1 constraint and contribute nothing to the
        # outlier check anyway).
        recent_orders = (
            await self._session.execute(
                select(Order)
                .where(Order.retailer_id == order.retailer_id)
                .where(Order.supplier_id == order.supplier_id)
                .where(Order.id != order_id)
                .order_by(Order.order_date.desc())
                .limit(recent_limit * 2)
            )
        ).scalars().all()
        recent_dtos: list[OrderDTO] = []
        for candidate in recent_orders:
            dto = await self._try_build_order_dto(candidate)
            if dto is not None:
                recent_dtos.append(dto)
            if len(recent_dtos) >= recent_limit:
                break

        agent_result = self._agent.analyze(
            AnalystAgentInput(order=current_dto, recent_orders=recent_dtos)
        )

        suggestion_id = uuid4()
        self._session.add(
            AgentSuggestion(
                id=suggestion_id,
                order_id=order_id,
                agent_type="analyst",
                action=agent_result.action,
                confidence=Decimal(str(round(agent_result.confidence, 3))),
                reasoning=agent_result.reasoning,
                anomalies_detected=agent_result.anomalies_detected,
                phoenix_trace_id=agent_result.phoenix_trace_id,
            )
        )
        await self._session.commit()

        return AnalyseOrderResult(
            suggestion_id=suggestion_id,
            order_id=order_id,
            action=agent_result.action,
            confidence=agent_result.confidence,
            reasoning=agent_result.reasoning,
            anomalies_detected=agent_result.anomalies_detected,
            phoenix_trace_id=agent_result.phoenix_trace_id,
            recent_orders_considered=len(recent_dtos),
        )

    async def _build_order_dto(self, order: Order) -> OrderDTO:
        """Reconstruct OrderDTO from ORM rows instead of raw_payload.

        Seed-generated orders have a placeholder raw_payload, so we never
        rely on it. Sample-uploaded orders could use raw_payload, but going
        through the ORM uniformly keeps the code path single."""
        retailer = await self._session.get(Retailer, order.retailer_id)
        supplier = await self._session.get(Supplier, order.supplier_id)
        currency = await self._session.get(Currency, order.currency_id)
        line_items = (
            await self._session.execute(
                select(OrderLineItem)
                .where(OrderLineItem.order_id == order.id)
                .order_by(OrderLineItem.line_number)
            )
        ).scalars().all()

        return OrderDTO(
            order_number=order.order_number,
            order_date=order.order_date,
            expected_delivery_date=order.expected_delivery_date,
            retailer_code=retailer.code,
            retailer_name=retailer.name,
            supplier_code=supplier.code,
            supplier_name=supplier.name,
            currency_code=currency.code,
            total_amount=order.total_amount,
            line_items=[
                OrderLineItemDTO(
                    line_number=li.line_number,
                    product_code=li.product_code,
                    product_name=li.product_name,
                    quantity=li.quantity,
                    unit_price=li.unit_price,
                    line_total=li.line_total,
                )
                for li in line_items
            ],
        )

    async def _try_build_order_dto(self, order: Order) -> OrderDTO | None:
        """Build a historical-context DTO, returning None when the order is
        unusable (e.g. seed-generated rows with no line items).

        Logged at debug level rather than warning — empty historical orders
        are expected from synthetic data, not a real error."""
        try:
            return await self._build_order_dto(order)
        except Exception as exc:  # noqa: BLE001
            _log.debug("Skipping order %s as historical context: %s", order.id, exc)
            return None
