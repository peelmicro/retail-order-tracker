"""Analyst Agent tests — mocked so we never burn Anthropic credits.

A real end-to-end check is a manual step once recent-order history is wired
up in Phase 5 (order ingestion).
"""

from unittest.mock import MagicMock, patch

import pytest

from src.application.dtos import OrderDTO, OrderLineItemDTO
from src.application.ports.analyst_agent import AnalystAgentInput
from src.domain.enums import AgentAction
from src.infrastructure.agents.errors import ApiKeyMissingError


def _order(num: str = "PO-TEST-001") -> OrderDTO:
    return OrderDTO(
        order_number=num,
        order_date="2026-04-23T10:00:00Z",
        retailer_code="TEST-R",
        retailer_name="Test Retailer",
        supplier_code="TEST-S",
        supplier_name="Test Supplier",
        currency_code="EUR",
        total_amount=10_000,
        line_items=[
            OrderLineItemDTO(
                line_number=1,
                product_code="X",
                quantity=1,
                unit_price=10_000,
                line_total=10_000,
            )
        ],
    )


def _mock_tool_response(tool_name: str, args: dict):
    response = MagicMock()
    response.tool_calls = [{"name": tool_name, "args": args}]
    return response


def test_rejects_missing_api_key() -> None:
    from src.infrastructure.agents.analyst_agent import ClaudeAnalystAgent

    with patch("src.infrastructure.agents.analyst_agent.settings") as mock_settings:
        mock_settings.anthropic_api_key = ""
        with pytest.raises(ApiKeyMissingError):
            ClaudeAnalystAgent(api_key="")
        with pytest.raises(ApiKeyMissingError):
            ClaudeAnalystAgent(api_key="your-api-key-here")


def test_analyze_returns_approve_when_tool_called() -> None:
    with patch("src.infrastructure.agents.analyst_agent.ChatAnthropic") as mock_chat_cls:
        llm_with_tools = MagicMock()
        llm_with_tools.invoke.return_value = _mock_tool_response(
            "approve_order",
            {
                "reasoning": "Order matches historical pattern",
                "anomalies_detected": [],
                "confidence": 0.95,
            },
        )
        mock_chat_cls.return_value.bind_tools.return_value = llm_with_tools

        from src.infrastructure.agents.analyst_agent import ClaudeAnalystAgent

        agent = ClaudeAnalystAgent(api_key="sk-test-stub")
        result = agent.analyze(AnalystAgentInput(order=_order(), recent_orders=[]))

        assert result.action == AgentAction.APPROVE
        assert result.confidence == pytest.approx(0.95)
        assert result.reasoning == "Order matches historical pattern"
        assert result.anomalies_detected == []


def test_analyze_returns_escalate_with_anomalies() -> None:
    with patch("src.infrastructure.agents.analyst_agent.ChatAnthropic") as mock_chat_cls:
        llm_with_tools = MagicMock()
        llm_with_tools.invoke.return_value = _mock_tool_response(
            "escalate_order",
            {
                "reasoning": "Quantity 100x historical average",
                "anomalies_detected": ["quantity_anomaly", "unknown_sku"],
                "confidence": 0.88,
            },
        )
        mock_chat_cls.return_value.bind_tools.return_value = llm_with_tools

        from src.infrastructure.agents.analyst_agent import ClaudeAnalystAgent

        agent = ClaudeAnalystAgent(api_key="sk-test-stub")
        result = agent.analyze(
            AnalystAgentInput(order=_order(), recent_orders=[_order(), _order()])
        )

        assert result.action == AgentAction.ESCALATE
        assert result.anomalies_detected == ["quantity_anomaly", "unknown_sku"]
        assert result.confidence == pytest.approx(0.88)


def test_binds_three_tools_with_any_choice() -> None:
    with patch("src.infrastructure.agents.analyst_agent.ChatAnthropic") as mock_chat_cls:
        from src.infrastructure.agents.analyst_agent import ClaudeAnalystAgent

        ClaudeAnalystAgent(api_key="sk-test-stub")

        bind_call = mock_chat_cls.return_value.bind_tools
        bind_call.assert_called_once()
        tools_arg = bind_call.call_args.args[0]
        assert len(tools_arg) == 3
        assert {t.name for t in tools_arg} == {
            "approve_order",
            "request_clarification",
            "escalate_order",
        }
        assert bind_call.call_args.kwargs.get("tool_choice") == "any"


def test_raises_when_llm_returns_no_tool_call() -> None:
    with patch("src.infrastructure.agents.analyst_agent.ChatAnthropic") as mock_chat_cls:
        empty_response = MagicMock()
        empty_response.tool_calls = []
        llm_with_tools = MagicMock()
        llm_with_tools.invoke.return_value = empty_response
        mock_chat_cls.return_value.bind_tools.return_value = llm_with_tools

        from src.infrastructure.agents.analyst_agent import ClaudeAnalystAgent

        agent = ClaudeAnalystAgent(api_key="sk-test-stub")
        with pytest.raises(RuntimeError, match="did not call a tool"):
            agent.analyze(AnalystAgentInput(order=_order()))
