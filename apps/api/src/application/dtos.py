"""Canonical DTOs shared across parsers, agents, persistence, and the API.

All monetary amounts are in minor units (integer cents) — never floats.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Project-wide Pydantic base. JSON output is camelCase; Python attrs stay snake_case."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


CurrencyCode = Annotated[
    str,
    StringConstraints(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$"),
]


class OrderLineItemDTO(CamelModel):
    line_number: int = Field(ge=1)
    product_code: str = Field(min_length=1, max_length=100)
    product_name: str | None = Field(default=None, max_length=300)
    quantity: int = Field(gt=0)
    unit_price: int = Field(ge=0, description="Minor units (cents)")
    line_total: int = Field(ge=0, description="Minor units (cents)")


class OrderDTO(CamelModel):
    """Normalised purchase order — the canonical contract every parser returns."""

    order_number: str = Field(min_length=1, max_length=100)
    order_date: datetime
    expected_delivery_date: datetime | None = None

    retailer_code: str = Field(min_length=1, max_length=50)
    retailer_name: str = Field(min_length=1, max_length=200)

    supplier_code: str = Field(min_length=1, max_length=50)
    supplier_name: str = Field(min_length=1, max_length=200)

    currency_code: CurrencyCode
    total_amount: int = Field(ge=0, description="Minor units (cents)")

    line_items: list[OrderLineItemDTO] = Field(min_length=1)

    # Format-specific extras that don't belong on the core contract
    # (e.g., EDIFACT message reference, XML namespace metadata).
    raw_fields: dict[str, Any] = Field(default_factory=dict)

    # Only the PDF Parser Agent populates this; deterministic parsers leave it None.
    parsing_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
