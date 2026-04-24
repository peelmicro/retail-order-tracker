"""Port for the Analyst Agent — decides what to do with a purchase order.

The agent compares the current order against recent history for the same
retailer-supplier pair, detects anomalies, and picks one of three actions:
approve, request clarification, or escalate.
"""

from typing import Protocol, runtime_checkable

from pydantic import Field

from src.application.dtos import CamelModel, OrderDTO
from src.domain.enums import AgentAction


class AnalystAgentInput(CamelModel):
    order: OrderDTO
    recent_orders: list[OrderDTO] = Field(default_factory=list)


class AnalystAgentResult(CamelModel):
    action: AgentAction
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    anomalies_detected: list[str] = Field(default_factory=list)
    # Populated from the current OpenTelemetry span so the DB can deep-link
    # to the Phoenix trace viewer.
    phoenix_trace_id: str | None = None


@runtime_checkable
class AnalystAgent(Protocol):
    def analyze(self, input: AnalystAgentInput) -> AnalystAgentResult: ...
