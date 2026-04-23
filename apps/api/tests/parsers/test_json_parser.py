from src.infrastructure.parsers.json_parser import JsonOrderParser


def test_supports_json_extension() -> None:
    parser = JsonOrderParser()
    assert parser.supports("order.json")
    assert parser.supports("Order.JSON")
    assert parser.supports("o.txt", mime_type="application/json")
    assert not parser.supports("order.csv")


def test_parses_carrefour_sample(samples_dir) -> None:
    parser = JsonOrderParser()
    file_bytes = (samples_dir / "sample-json.json").read_bytes()

    order = parser.parse(file_bytes, "sample-json.json")

    assert order.order_number == "PO-CARREFOUR-000123"
    assert order.retailer_code == "CARREFOUR-ES"
    assert order.retailer_name == "Carrefour España SA"
    assert order.supplier_code == "IBERIAN-FOODS"
    assert order.currency_code == "EUR"
    assert order.total_amount == 124_250
    assert order.parsing_confidence is None

    assert len(order.line_items) == 2
    first = order.line_items[0]
    assert first.line_number == 1
    assert first.product_code == "SKU-OIL-EVO-1L"
    assert first.product_name == "Extra Virgin Olive Oil 1L"
    assert first.quantity == 100
    assert first.unit_price == 595
    assert first.line_total == 59_500

    assert order.raw_fields == {"source_format": "json"}
