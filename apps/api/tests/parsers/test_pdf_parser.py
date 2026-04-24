"""PdfOrderParser is a thin delegate — we only verify the OrderParser
contract and that it forwards bytes to the injected ParserAgent."""

from unittest.mock import MagicMock

from src.application.dtos import OrderDTO, OrderLineItemDTO
from src.infrastructure.parsers.pdf_parser import PdfOrderParser


def test_supports_pdf_extension_and_mime() -> None:
    parser = PdfOrderParser(agent=MagicMock())
    assert parser.supports("order.pdf")
    assert parser.supports("Order.PDF")
    assert parser.supports("file.bin", mime_type="application/pdf")
    assert not parser.supports("order.json")
    assert not parser.supports("order.csv", mime_type="text/csv")


def test_delegates_bytes_to_agent() -> None:
    fake_order = OrderDTO(
        order_number="PO-PDF-DELEGATE",
        order_date="2026-04-22T00:00:00Z",
        retailer_code="R",
        retailer_name="R Co",
        supplier_code="S",
        supplier_name="S Co",
        currency_code="EUR",
        total_amount=500,
        line_items=[
            OrderLineItemDTO(
                line_number=1, product_code="X", quantity=1, unit_price=500, line_total=500
            )
        ],
    )
    agent = MagicMock()
    agent.parse_pdf.return_value = fake_order

    parser = PdfOrderParser(agent=agent)
    pdf_bytes = b"%PDF-1.4 bytes"
    result = parser.parse(pdf_bytes, "sample.pdf")

    agent.parse_pdf.assert_called_once_with(pdf_bytes)
    assert result.order_number == "PO-PDF-DELEGATE"


def test_dispatcher_includes_pdf_parser_when_agent_provided() -> None:
    from src.infrastructure.parsers.dispatcher import default_dispatcher

    # Without an agent → 4 deterministic parsers
    base = default_dispatcher()
    assert not any(isinstance(p, PdfOrderParser) for p in base._parsers)

    # With an agent → PDF parser is appended
    with_agent = default_dispatcher(parser_agent=MagicMock())
    assert any(isinstance(p, PdfOrderParser) for p in with_agent._parsers)
