from src.infrastructure.parsers.xml_parser import XmlOrderParser


def test_supports_xml_extension() -> None:
    parser = XmlOrderParser()
    assert parser.supports("order.xml")
    assert parser.supports("o.bin", mime_type="application/xml")
    assert parser.supports("o.bin", mime_type="text/xml")
    assert not parser.supports("order.json")


def test_parses_facturae_sample(samples_dir) -> None:
    parser = XmlOrderParser()
    file_bytes = (samples_dir / "sample-xml-facturae.xml").read_bytes()

    order = parser.parse(file_bytes, "sample-xml-facturae.xml")

    assert order.order_number == "PO-ELCORTE-000789"
    assert order.retailer_code == "ELCORTE-ES"
    assert order.retailer_name == "El Corte Inglés SA"
    assert order.supplier_code == "FASHION-PLUS"
    assert order.currency_code == "EUR"
    # 2996.00 EUR → 299600 minor units
    assert order.total_amount == 299_600

    assert len(order.line_items) == 2
    first = order.line_items[0]
    assert first.product_code == "SHIRT-COTTON-M"
    assert first.quantity == 50
    # 29.95 EUR → 2995 minor units
    assert first.unit_price == 2_995
    # 1497.50 EUR → 149750 minor units
    assert first.line_total == 149_750

    assert order.raw_fields == {"source_format": "xml", "schema": "purchaseorder-v1"}
