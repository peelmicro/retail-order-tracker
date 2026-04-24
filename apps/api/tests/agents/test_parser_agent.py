"""Parser Agent tests — all mocked so we never burn Anthropic credits.

A real end-to-end check happens manually once a sample PDF exists (Phase 4.2).
"""

from unittest.mock import MagicMock, patch

import pytest

from src.application.dtos import OrderDTO, OrderLineItemDTO


def _fake_order() -> OrderDTO:
    return OrderDTO(
        order_number="PO-PDF-000001",
        order_date="2026-04-20T10:00:00Z",
        retailer_code="PDF-RET",
        retailer_name="PDF Retailer SA",
        supplier_code="PDF-SUP",
        supplier_name="PDF Supplier SL",
        currency_code="EUR",
        total_amount=10_000,
        line_items=[
            OrderLineItemDTO(
                line_number=1,
                product_code="SKU-1",
                product_name="PDF Product",
                quantity=2,
                unit_price=5_000,
                line_total=10_000,
            )
        ],
        parsing_confidence=0.92,
    )


def test_rejects_missing_api_key() -> None:
    """Must raise when neither the constructor arg nor settings has a real key.

    We patch settings so the test is deterministic regardless of whether the
    developer has a real ANTHROPIC_API_KEY in their local .env."""
    from src.infrastructure.agents.parser_agent import ApiKeyMissingError, ClaudeParserAgent

    with patch("src.infrastructure.agents.parser_agent.settings") as mock_settings:
        mock_settings.anthropic_api_key = ""
        # Empty param falls through to (patched-empty) settings → raises
        with pytest.raises(ApiKeyMissingError):
            ClaudeParserAgent(api_key="")
        # Placeholder param is rejected regardless of settings
        with pytest.raises(ApiKeyMissingError):
            ClaudeParserAgent(api_key="your-api-key-here")


def test_sends_pdf_as_base64_document_block_and_returns_order() -> None:
    with patch(
        "src.infrastructure.agents.parser_agent.ChatAnthropic"
    ) as mock_chat_cls:
        # ChatAnthropic(...).with_structured_output(OrderDTO).invoke(...) -> OrderDTO
        structured_llm = MagicMock()
        structured_llm.invoke.return_value = _fake_order()
        mock_chat_cls.return_value.with_structured_output.return_value = structured_llm

        from src.infrastructure.agents.parser_agent import ClaudeParserAgent

        agent = ClaudeParserAgent(api_key="sk-test-stub")
        result = agent.parse_pdf(b"%PDF-1.4 fake pdf bytes")

        assert result.order_number == "PO-PDF-000001"
        assert result.parsing_confidence == pytest.approx(0.92)

        # Verify the LLM was instantiated once with temperature 0
        mock_chat_cls.assert_called_once()
        kwargs = mock_chat_cls.call_args.kwargs
        assert kwargs["temperature"] == 0.0
        assert kwargs["api_key"] == "sk-test-stub"

        # Verify the messages passed to invoke include a PDF document block
        messages = structured_llm.invoke.call_args.args[0]
        assert len(messages) == 2  # system + human
        human = messages[1]
        assert isinstance(human.content, list)
        doc_block = human.content[0]
        assert doc_block["type"] == "document"
        assert doc_block["source"]["type"] == "base64"
        assert doc_block["source"]["media_type"] == "application/pdf"
        # base64 of b"%PDF-1.4 fake pdf bytes"
        import base64
        expected = base64.standard_b64encode(b"%PDF-1.4 fake pdf bytes").decode("utf-8")
        assert doc_block["source"]["data"] == expected
        text_block = human.content[1]
        assert text_block["type"] == "text"


def test_structured_output_binds_order_dto() -> None:
    with patch(
        "src.infrastructure.agents.parser_agent.ChatAnthropic"
    ) as mock_chat_cls:
        mock_chat_cls.return_value.with_structured_output.return_value = MagicMock(
            invoke=MagicMock(return_value=_fake_order())
        )

        from src.infrastructure.agents.parser_agent import ClaudeParserAgent

        ClaudeParserAgent(api_key="sk-test-stub")

        # with_structured_output should have been called with OrderDTO
        with_struct = mock_chat_cls.return_value.with_structured_output
        with_struct.assert_called_once_with(OrderDTO)
