"""XML parser — namespaced PurchaseOrder schema using lxml + XPath.

The Spanish Facturae 3.2.2 standard covers invoices, not purchase orders,
so this parser uses a Facturae-flavoured custom PO schema suitable for the
assessment. Swapping in a real Facturae handler for invoices would be a
separate parser behind the same OrderParser protocol.
"""

from decimal import Decimal

from lxml import etree

from src.application.dtos import OrderDTO, OrderLineItemDTO

NS = {"po": "urn:edi:purchaseorder:v1"}


def _to_minor_units(value: str) -> int:
    """Convert a decimal major-unit string (e.g. '29.95') to minor units (2995)."""
    return int(Decimal(value) * 100)


def _xtext(node, xpath: str) -> str:
    """Return the text of the first XPath match. Handles both element selectors
    (which return lxml Element objects) and text()/@attr selectors (which
    return strings)."""
    results = node.xpath(xpath, namespaces=NS)
    if not results:
        raise ValueError(f"XPath {xpath!r} returned no nodes")
    first = results[0]
    if hasattr(first, "text"):
        return (first.text or "").strip()
    return str(first).strip()


class XmlOrderParser:
    name = "xml"
    extensions = (".xml",)

    def supports(self, filename: str, mime_type: str | None = None) -> bool:
        if filename.lower().endswith(self.extensions):
            return True
        if mime_type and mime_type in ("application/xml", "text/xml"):
            return True
        return False

    def parse(self, file_bytes: bytes, filename: str) -> OrderDTO:
        root = etree.fromstring(file_bytes)

        line_items: list[OrderLineItemDTO] = []
        for item in root.xpath("./po:Items/po:Item", namespaces=NS):
            line_items.append(
                OrderLineItemDTO(
                    line_number=int(item.get("lineNumber")),
                    product_code=_xtext(item, "./po:ProductCode"),
                    product_name=_xtext(item, "./po:ProductName"),
                    quantity=int(_xtext(item, "./po:Quantity")),
                    unit_price=_to_minor_units(_xtext(item, "./po:UnitPrice")),
                    line_total=_to_minor_units(_xtext(item, "./po:LineTotal")),
                )
            )

        return OrderDTO(
            order_number=_xtext(root, "./po:Header/po:OrderNumber"),
            order_date=_xtext(root, "./po:Header/po:OrderDate"),
            expected_delivery_date=_xtext(root, "./po:Header/po:ExpectedDeliveryDate"),
            retailer_code=_xtext(root, "./po:Buyer/po:Code"),
            retailer_name=_xtext(root, "./po:Buyer/po:Name"),
            supplier_code=_xtext(root, "./po:Seller/po:Code"),
            supplier_name=_xtext(root, "./po:Seller/po:Name"),
            currency_code=_xtext(root, "./po:Header/po:Currency"),
            total_amount=_to_minor_units(_xtext(root, "./po:TotalAmount")),
            line_items=line_items,
            raw_fields={"source_format": "xml", "schema": "purchaseorder-v1"},
        )
