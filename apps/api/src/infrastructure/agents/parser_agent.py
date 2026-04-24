"""Claude-backed Parser Agent — extracts OrderDTO from a PDF.

Uses LangChain's ChatAnthropic with structured output (so Claude returns
a validated OrderDTO directly) and multimodal PDF input. Every invocation
emits an OpenTelemetry span with order / confidence attributes for Phoenix.
"""

from __future__ import annotations

import base64
import logging

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from opentelemetry import trace

from src.application.dtos import OrderDTO
from src.config import settings
from src.infrastructure.agents.errors import (  # noqa: F401 — re-exported for backwards compat
    ApiKeyMissingError,
    is_placeholder_api_key,
)
from src.infrastructure.observability.phoenix import init_phoenix

_log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You extract structured purchase order data from PDF documents.

Extract the following fields:
- order_number
- order_date (ISO 8601)
- expected_delivery_date (ISO 8601, optional)
- retailer_code and retailer_name (the buyer)
- supplier_code and supplier_name (the seller)
- currency_code (ISO 4217, 3 uppercase letters, e.g. EUR)
- total_amount as an integer in minor units — never a float
- line_items: each with line_number, product_code, product_name, quantity,
  unit_price (minor units), line_total (minor units)
- parsing_confidence: your self-reported confidence from 0.0 to 1.0

Return the result matching the provided schema exactly. Prefer inference over
returning null for required fields."""


class ClaudeParserAgent:
    """Multimodal PDF → OrderDTO extractor using Claude."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
    ) -> None:
        # Ensure Phoenix tracing is configured even when the agent is used
        # outside FastAPI (e.g. standalone scripts, pytest). Idempotent.
        init_phoenix(service_name="retail-order-tracker")

        resolved_key = api_key or settings.anthropic_api_key
        if is_placeholder_api_key(resolved_key):
            raise ApiKeyMissingError(
                "ANTHROPIC_API_KEY is not set. The Parser Agent requires a live key."
            )
        self._model = model
        self._llm = ChatAnthropic(
            model=model,
            api_key=resolved_key,
            temperature=0.0,
        ).with_structured_output(OrderDTO)
        self._tracer = trace.get_tracer(__name__)

    def parse_pdf(self, pdf_bytes: bytes) -> OrderDTO:
        b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
        message = HumanMessage(
            content=[
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": b64,
                    },
                },
                {"type": "text", "text": "Extract the purchase order from this PDF."},
            ]
        )

        with self._tracer.start_as_current_span("parser_agent.parse") as span:
            span.set_attribute("agent_type", "parser")
            span.set_attribute("model", self._model)
            span.set_attribute("input.pdf_size_bytes", len(pdf_bytes))

            order = self._llm.invoke([SystemMessage(content=SYSTEM_PROMPT), message])

            span.set_attribute("output.order_number", order.order_number or "")
            span.set_attribute("output.currency", order.currency_code or "")
            span.set_attribute("output.total_amount", order.total_amount or 0)
            span.set_attribute(
                "output.parsing_confidence",
                float(order.parsing_confidence or 0.0),
            )
            return order
