import pytest

from src.application.ports.order_parser import UnsupportedFormatError
from src.infrastructure.parsers.dispatcher import default_dispatcher


def test_dispatches_all_four_formats(samples_dir) -> None:
    dispatcher = default_dispatcher()
    cases = [
        ("sample-json.json", "PO-CARREFOUR-000123"),
        ("sample-xml-facturae.xml", "PO-ELCORTE-000789"),
        ("sample-csv.csv", "PO-LEROY-000456"),
        ("sample-edifact-carrefour.edi", "PO-CARREFOUR-000321"),
    ]
    for filename, expected_order_number in cases:
        file_bytes = (samples_dir / filename).read_bytes()
        order = dispatcher.dispatch(file_bytes, filename)
        assert order.order_number == expected_order_number, (
            f"Dispatcher produced wrong order number for {filename}"
        )


def test_unknown_extension_raises() -> None:
    dispatcher = default_dispatcher()
    with pytest.raises(UnsupportedFormatError):
        dispatcher.dispatch(b"anything", "order.txt")


def test_mime_type_can_override_extension(samples_dir) -> None:
    dispatcher = default_dispatcher()
    file_bytes = (samples_dir / "sample-json.json").read_bytes()
    # A .bin file served with JSON mime should still parse as JSON
    order = dispatcher.dispatch(file_bytes, "uploaded.bin", mime_type="application/json")
    assert order.order_number == "PO-CARREFOUR-000123"
