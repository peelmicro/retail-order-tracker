"""CSV parser — multi-row format with repeated header fields using pandas."""

from decimal import Decimal
from io import BytesIO

import pandas as pd

from src.application.dtos import OrderDTO, OrderLineItemDTO


def _to_minor_units(value: str | float) -> int:
    return int(Decimal(str(value)) * 100)


class CsvOrderParser:
    name = "csv"
    extensions = (".csv",)

    def supports(self, filename: str, mime_type: str | None = None) -> bool:
        if filename.lower().endswith(self.extensions):
            return True
        if mime_type and mime_type in ("text/csv", "application/csv"):
            return True
        return False

    def parse(self, file_bytes: bytes, filename: str) -> OrderDTO:
        df = pd.read_csv(BytesIO(file_bytes))
        if df.empty:
            raise ValueError(f"CSV file {filename!r} is empty")

        # Header fields are repeated on every row — take from the first.
        header = df.iloc[0]

        line_items = [
            OrderLineItemDTO(
                line_number=int(row["LineNumber"]),
                product_code=str(row["ProductCode"]),
                product_name=str(row["ProductName"]),
                quantity=int(row["Quantity"]),
                unit_price=_to_minor_units(row["UnitPrice"]),
                line_total=_to_minor_units(row["LineTotal"]),
            )
            for _, row in df.iterrows()
        ]

        total = sum(li.line_total for li in line_items)

        return OrderDTO(
            order_number=str(header["OrderNumber"]),
            order_date=str(header["OrderDate"]),
            expected_delivery_date=str(header["DeliveryDate"]),
            retailer_code=str(header["RetailerCode"]),
            retailer_name=str(header["RetailerName"]),
            supplier_code=str(header["SupplierCode"]),
            supplier_name=str(header["SupplierName"]),
            currency_code=str(header["Currency"]),
            total_amount=total,
            line_items=line_items,
            raw_fields={"source_format": "csv"},
        )
