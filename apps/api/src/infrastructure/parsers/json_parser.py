"""JSON parser — maps a Carrefour-style retailer schema onto OrderDTO.

Different retailers send different JSON shapes. This adapter handles the
schema used by the `sample-json.json` fixture; alternative schemas would
either be supported here with a dispatch on a discriminator field or get
their own parser.
"""

import json

from src.application.dtos import OrderDTO, OrderLineItemDTO


class JsonOrderParser:
    name = "json"
    extensions = (".json",)

    def supports(self, filename: str, mime_type: str | None = None) -> bool:
        if filename.lower().endswith(self.extensions):
            return True
        if mime_type and mime_type.startswith("application/json"):
            return True
        return False

    def parse(self, file_bytes: bytes, filename: str) -> OrderDTO:
        payload = json.loads(file_bytes.decode("utf-8"))

        line_items = [
            OrderLineItemDTO(
                line_number=item["no"],
                product_code=item["sku"],
                product_name=item.get("description"),
                quantity=item["qty"],
                unit_price=item["unitPriceMinor"],
                line_total=item["lineTotalMinor"],
            )
            for item in payload["lines"]
        ]

        return OrderDTO(
            order_number=payload["orderId"],
            order_date=payload["orderDate"],
            expected_delivery_date=payload.get("deliveryDate"),
            retailer_code=payload["buyer"]["code"],
            retailer_name=payload["buyer"]["name"],
            supplier_code=payload["seller"]["code"],
            supplier_name=payload["seller"]["name"],
            currency_code=payload["currency"],
            total_amount=payload["totalMinor"],
            line_items=line_items,
            raw_fields={"source_format": "json"},
        )
