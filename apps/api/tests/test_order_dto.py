from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.application.dtos import OrderDTO, OrderLineItemDTO


def _valid_order(**overrides) -> dict:
    base = {
        "order_number": "PO-12345",
        "order_date": datetime(2026, 4, 23, 10, 0, tzinfo=UTC),
        "retailer_code": "CARREFOUR-ES",
        "retailer_name": "Carrefour España",
        "supplier_code": "SUP-001",
        "supplier_name": "Iberian Foods SL",
        "currency_code": "EUR",
        "total_amount": 125_000,
        "line_items": [
            {
                "line_number": 1,
                "product_code": "SKU-A",
                "product_name": "Olive Oil 1L",
                "quantity": 10,
                "unit_price": 12_500,
                "line_total": 125_000,
            }
        ],
    }
    base.update(overrides)
    return base


def test_happy_path_construction() -> None:
    dto = OrderDTO.model_validate(_valid_order())
    assert dto.order_number == "PO-12345"
    assert dto.currency_code == "EUR"
    assert dto.total_amount == 125_000
    assert len(dto.line_items) == 1
    assert dto.parsing_confidence is None
    assert dto.raw_fields == {}


def test_json_serialises_with_camel_case_aliases() -> None:
    dto = OrderDTO.model_validate(_valid_order())
    payload = dto.model_dump(mode="json", by_alias=True)
    assert "orderNumber" in payload
    assert "lineItems" in payload
    assert "totalAmount" in payload
    assert "order_number" not in payload
    assert payload["lineItems"][0]["productCode"] == "SKU-A"


def test_json_accepts_camel_case_on_input() -> None:
    payload = {
        "orderNumber": "PO-9",
        "orderDate": "2026-04-23T10:00:00Z",
        "retailerCode": "R",
        "retailerName": "R name",
        "supplierCode": "S",
        "supplierName": "S name",
        "currencyCode": "USD",
        "totalAmount": 100,
        "lineItems": [
            {
                "lineNumber": 1,
                "productCode": "P",
                "quantity": 1,
                "unitPrice": 100,
                "lineTotal": 100,
            }
        ],
    }
    dto = OrderDTO.model_validate(payload)
    assert dto.order_number == "PO-9"
    assert dto.currency_code == "USD"
    assert dto.line_items[0].product_code == "P"


def test_rejects_lowercase_currency_code() -> None:
    with pytest.raises(ValidationError):
        OrderDTO.model_validate(_valid_order(currency_code="eur"))


def test_rejects_invalid_currency_length() -> None:
    with pytest.raises(ValidationError):
        OrderDTO.model_validate(_valid_order(currency_code="EURO"))


def test_rejects_negative_total() -> None:
    with pytest.raises(ValidationError):
        OrderDTO.model_validate(_valid_order(total_amount=-1))


def test_rejects_empty_line_items() -> None:
    with pytest.raises(ValidationError):
        OrderDTO.model_validate(_valid_order(line_items=[]))


def test_rejects_zero_quantity_line_item() -> None:
    with pytest.raises(ValidationError):
        OrderLineItemDTO.model_validate(
            {
                "lineNumber": 1,
                "productCode": "P",
                "quantity": 0,
                "unitPrice": 100,
                "lineTotal": 0,
            }
        )


def test_parsing_confidence_bounds() -> None:
    assert OrderDTO.model_validate(_valid_order(parsing_confidence=0.0)).parsing_confidence == 0.0
    assert OrderDTO.model_validate(_valid_order(parsing_confidence=1.0)).parsing_confidence == 1.0

    with pytest.raises(ValidationError):
        OrderDTO.model_validate(_valid_order(parsing_confidence=1.5))
    with pytest.raises(ValidationError):
        OrderDTO.model_validate(_valid_order(parsing_confidence=-0.1))
