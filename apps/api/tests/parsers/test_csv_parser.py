from src.infrastructure.parsers.csv_parser import CsvOrderParser


def test_supports_csv_extension() -> None:
    parser = CsvOrderParser()
    assert parser.supports("order.csv")
    assert parser.supports("o.bin", mime_type="text/csv")
    assert not parser.supports("order.xml")


def test_parses_leroy_merlin_sample(samples_dir) -> None:
    parser = CsvOrderParser()
    file_bytes = (samples_dir / "sample-csv.csv").read_bytes()

    order = parser.parse(file_bytes, "sample-csv.csv")

    assert order.order_number == "PO-LEROY-000456"
    assert order.retailer_code == "LEROY-ES"
    assert order.retailer_name == "Leroy Merlin España"
    assert order.supplier_code == "TOOLS-PLUS"
    assert order.currency_code == "EUR"

    assert len(order.line_items) == 3
    # Line 1: 25 × 89.00 = 2225.00 → 222_500 minor units
    assert order.line_items[0].unit_price == 8_900
    assert order.line_items[0].line_total == 222_500
    # Line 2: 100 × 12.95 = 1295.00 → 129_500 minor units
    assert order.line_items[1].unit_price == 1_295
    assert order.line_items[1].line_total == 129_500
    # Line 3: 200 × 4.95 = 990.00 → 99_000 minor units
    assert order.line_items[2].unit_price == 495
    assert order.line_items[2].line_total == 99_000

    # total derived from line items = 451_000 minor units
    assert order.total_amount == 451_000
