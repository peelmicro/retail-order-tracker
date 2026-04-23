from datetime import UTC, datetime

from src.infrastructure.parsers.edifact_parser import EdifactOrderParser


def test_supports_edi_extension() -> None:
    parser = EdifactOrderParser()
    assert parser.supports("order.edi")
    assert parser.supports("order.edifact")
    assert not parser.supports("order.xml")


def test_parses_carrefour_d96a_sample(samples_dir) -> None:
    parser = EdifactOrderParser()
    file_bytes = (samples_dir / "sample-edifact-carrefour.edi").read_bytes()

    order = parser.parse(file_bytes, "sample-edifact-carrefour.edi")

    assert order.order_number == "PO-CARREFOUR-000321"
    assert order.order_date == datetime(2026, 4, 22, tzinfo=UTC)
    assert order.expected_delivery_date == datetime(2026, 4, 29, tzinfo=UTC)
    assert order.retailer_code == "CARREFOUR-ES"
    assert order.retailer_name == "Carrefour España SA"
    assert order.supplier_code == "IBERIAN-FOODS"
    assert order.supplier_name == "Iberian Foods SL"
    assert order.currency_code == "EUR"

    assert len(order.line_items) == 2
    line1, line2 = order.line_items

    assert line1.product_code == "SKU-OIL-EVO-500"
    assert line1.product_name == "Extra Virgin Olive Oil 500ml"
    assert line1.quantity == 200
    assert line1.unit_price == 395
    assert line1.line_total == 79_000

    assert line2.product_code == "SKU-WATER-SPK-6PACK"
    assert line2.quantity == 500
    assert line2.unit_price == 350
    assert line2.line_total == 175_000

    assert order.total_amount == 254_000
    assert order.raw_fields == {"source_format": "edifact", "standard": "D.96A"}
