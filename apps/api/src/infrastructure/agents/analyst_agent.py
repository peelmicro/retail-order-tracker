"""Claude-backed Analyst Agent — picks an action for a purchase order.

Uses tool calling with 3 mutually exclusive tools. `bind_tools(tool_choice="any")`
forces Claude to call exactly one of them, so extracting the tool name and
arguments gives us the agent's decision.
"""

from __future__ import annotations

import json
import logging

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from opentelemetry import trace

from src.application.ports.analyst_agent import AnalystAgentInput, AnalystAgentResult
from src.config import settings
from src.domain.enums import AgentAction
from src.infrastructure.agents.errors import ApiKeyMissingError, is_placeholder_api_key
from src.infrastructure.observability.phoenix import init_phoenix

_log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are an experienced EDI operations analyst reviewing retail purchase orders.

You have exactly 3 tools. Call EXACTLY ONE of them:
  - approve_order: the order looks normal and should be automatically approved
  - request_clarification: there are issues to resolve with buyer or supplier
    before approval, but nothing catastrophic
  - escalate_order: serious anomalies requiring human escalation (possible
    fraud, gross errors, or out-of-policy values)

For every decision include:
  - reasoning: clear, concise explanation (1-3 sentences)
  - anomalies_detected: specific anomalies found (empty list if none)
  - confidence: your confidence in the decision, 0.0 to 1.0

Compare the current order against the recent orders for the same retailer and
supplier pair. Common anomalies:
  - Quantities unusually large or small compared to historical averages
  - Unit prices significantly off historical norm
  - Missing or malformed data fields
  - Order or delivery dates that do not make business sense
  - Product codes never seen before for this pair (could be a new SKU or a typo)
"""


@tool
def approve_order(reasoning: str, anomalies_detected: list[str], confidence: float) -> dict:
    """Approve the order for automatic processing. Use when the order is
    consistent with recent history and no anomalies need attention."""
    return {
        "action": AgentAction.APPROVE.value,
        "reasoning": reasoning,
        "anomalies_detected": anomalies_detected,
        "confidence": confidence,
    }


@tool
def request_clarification(
    reasoning: str, anomalies_detected: list[str], confidence: float
) -> dict:
    """Request clarification from the buyer or supplier. Use when there are
    specific issues to resolve (ambiguous field, unexpected SKU) but no
    evidence of a serious problem."""
    return {
        "action": AgentAction.REQUEST_CLARIFICATION.value,
        "reasoning": reasoning,
        "anomalies_detected": anomalies_detected,
        "confidence": confidence,
    }


@tool
def escalate_order(reasoning: str, anomalies_detected: list[str], confidence: float) -> dict:
    """Escalate to a human operator. Use when anomalies suggest possible fraud,
    serious errors, or out-of-policy values that a machine should not approve."""
    return {
        "action": AgentAction.ESCALATE.value,
        "reasoning": reasoning,
        "anomalies_detected": anomalies_detected,
        "confidence": confidence,
    }


_TOOL_NAME_TO_ACTION = {
    "approve_order": AgentAction.APPROVE,
    "request_clarification": AgentAction.REQUEST_CLARIFICATION,
    "escalate_order": AgentAction.ESCALATE,
}


class ClaudeAnalystAgent:
    """OrderDTO + history → decision via Claude tool calling."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
    ) -> None:
        init_phoenix(service_name="retail-order-tracker")

        resolved_key = api_key or settings.anthropic_api_key
        if is_placeholder_api_key(resolved_key):
            raise ApiKeyMissingError(
                "ANTHROPIC_API_KEY is not set. The Analyst Agent requires a live key."
            )
        self._model = model
        self._llm = ChatAnthropic(
            model=model,
            api_key=resolved_key,
            temperature=0.0,
        ).bind_tools(
            [approve_order, request_clarification, escalate_order],
            tool_choice="any",
        )
        self._tracer = trace.get_tracer(__name__)

    def analyze(self, input: AnalystAgentInput) -> AnalystAgentResult:
        with self._tracer.start_as_current_span("analyst_agent.analyze") as span:
            span.set_attribute("agent_type", "analyst")
            span.set_attribute("model", self._model)
            span.set_attribute("input.order_number", input.order.order_number)
            span.set_attribute("input.retailer_code", input.order.retailer_code)
            span.set_attribute("input.supplier_code", input.order.supplier_code)
            span.set_attribute("input.recent_orders_count", len(input.recent_orders))

            user_message = _format_context(input)

            response = self._llm.invoke(
                [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=user_message),
                ]
            )

            if not getattr(response, "tool_calls", None):
                raise RuntimeError(
                    "Analyst Agent did not call a tool — LLM returned text only"
                )

            tool_call = response.tool_calls[0]
            tool_name = tool_call["name"]
            args = tool_call.get("args", {})

            action = _TOOL_NAME_TO_ACTION.get(tool_name)
            if action is None:
                raise RuntimeError(f"Analyst Agent called unknown tool: {tool_name}")

            result = AnalystAgentResult(
                action=action,
                confidence=float(args.get("confidence", 0.5)),
                reasoning=str(args.get("reasoning", "")),
                anomalies_detected=list(args.get("anomalies_detected", [])),
                phoenix_trace_id=_current_trace_id_hex(span),
            )

            span.set_attribute("output.action", action.value)
            span.set_attribute("output.confidence", result.confidence)
            span.set_attribute("output.anomalies_count", len(result.anomalies_detected))
            return result


def _format_context(input: AnalystAgentInput) -> str:
    current = input.order.model_dump(mode="json", by_alias=True)
    recent = [o.model_dump(mode="json", by_alias=True) for o in input.recent_orders]
    return (
        "Analyze this purchase order and decide what to do with it.\n\n"
        f"CURRENT ORDER:\n{json.dumps(current, indent=2)}\n\n"
        f"RECENT ORDERS FOR THIS RETAILER-SUPPLIER PAIR ({len(recent)} orders):\n"
        f"{json.dumps(recent, indent=2)}\n\n"
        "Call exactly one of the 3 tools with your decision."
    )


def _current_trace_id_hex(span) -> str | None:
    ctx = span.get_span_context()
    if not ctx.is_valid:
        return None
    return f"{ctx.trace_id:032x}"
