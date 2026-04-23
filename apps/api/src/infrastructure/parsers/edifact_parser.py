"""EDIFACT D.96A ORDERS parser using pydifact.

Real EDIFACT messages used by Carrefour, El Corte Inglés, and Leroy Merlin
in production. The relevant segments for purchase orders are:

  BGM   beginning of message — document type (220 = order) + PO number
  DTM   date / time — 137 = document date, 2 = expected delivery date
  NAD   name and address — BY = buyer, SU = supplier
  CUX   currency reference
  LIN   line-item header with SKU
  IMD   item description (product name)
  QTY   quantity — 21 = ordered quantity
  PRI   price — AAA = net unit price (minor units in this project)
  UNS / CNT / UNT / UNZ   summary and trailers
"""

from datetime import UTC, datetime

from pydifact.segmentcollection import Interchange

from src.application.dtos import OrderDTO, OrderLineItemDTO


def _parse_edifact_date(date_str: str) -> datetime:
    """YYYYMMDD → timezone-aware datetime at midnight UTC."""
    return datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=UTC)


def _component(element, idx: int, default: str = "") -> str:
    """Pydifact returns elements as strings (single component) or lists (composite);
    this normalises either into a single string at the requested index."""
    if isinstance(element, list):
        if idx < len(element) and element[idx] is not None:
            return str(element[idx])
        return default
    if idx == 0 and isinstance(element, str):
        return element
    return default


class EdifactOrderParser:
    name = "edifact"
    extensions = (".edi", ".edifact")

    def supports(self, filename: str, mime_type: str | None = None) -> bool:
        return filename.lower().endswith(self.extensions)

    def parse(self, file_bytes: bytes, filename: str) -> OrderDTO:
        content = file_bytes.decode("utf-8")
        interchange = Interchange.from_str(content)

        order_number = ""
        order_date: datetime | None = None
        delivery_date: datetime | None = None
        currency_code = "EUR"
        retailer_code = ""
        retailer_name = ""
        supplier_code = ""
        supplier_name = ""
        line_items: list[OrderLineItemDTO] = []
        current: dict | None = None

        def flush_current() -> None:
            nonlocal current
            if current is None:
                return
            current["line_total"] = current["quantity"] * current["unit_price"]
            line_items.append(OrderLineItemDTO(**current))
            current = None

        for segment in interchange.segments:
            tag = segment.tag
            els = segment.elements

            if tag == "BGM":
                order_number = _component(els, 1) if len(els) > 1 else ""

            elif tag == "DTM":
                dtm = els[0] if els else []
                qualifier = _component(dtm, 0)
                date_str = _component(dtm, 1)
                if date_str:
                    if qualifier == "137":
                        order_date = _parse_edifact_date(date_str)
                    elif qualifier == "2":
                        delivery_date = _parse_edifact_date(date_str)

            elif tag == "NAD":
                party = _component(els, 0)
                code_info = els[1] if len(els) > 1 else ""
                code = _component(code_info, 0)
                name = ""
                if len(els) > 4:
                    name = _component(els[4], 0)
                if not name and len(els) > 3:
                    name = _component(els[3], 0)
                if party == "BY":
                    retailer_code, retailer_name = code, name
                elif party == "SU":
                    supplier_code, supplier_name = code, name

            elif tag == "CUX":
                cux = els[0] if els else []
                if _component(cux, 0) == "2":
                    currency_code = _component(cux, 1) or currency_code

            elif tag == "LIN":
                flush_current()
                line_no = _component(els, 0) or str(len(line_items) + 1)
                item_info = els[2] if len(els) > 2 else ""
                current = {
                    "line_number": int(line_no),
                    "product_code": _component(item_info, 0),
                    "product_name": None,
                    "quantity": 0,
                    "unit_price": 0,
                }

            elif tag == "IMD" and current is not None:
                imd = els[2] if len(els) > 2 else ""
                description = _component(imd, 3)
                current["product_name"] = description or None

            elif tag == "QTY" and current is not None:
                qty = els[0] if els else []
                if _component(qty, 0) == "21":
                    current["quantity"] = int(_component(qty, 1) or "0")

            elif tag == "PRI" and current is not None:
                pri = els[0] if els else []
                if _component(pri, 0) == "AAA":
                    current["unit_price"] = int(_component(pri, 1) or "0")

            elif tag in ("UNS", "CNT", "UNT"):
                flush_current()

        flush_current()

        total = sum(li.line_total for li in line_items)

        return OrderDTO(
            order_number=order_number,
            order_date=order_date,
            expected_delivery_date=delivery_date,
            retailer_code=retailer_code,
            retailer_name=retailer_name,
            supplier_code=supplier_code,
            supplier_name=supplier_name,
            currency_code=currency_code,
            total_amount=total,
            line_items=line_items,
            raw_fields={"source_format": "edifact", "standard": "D.96A"},
        )
