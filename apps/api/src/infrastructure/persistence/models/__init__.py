"""Re-export all models so Alembic's target_metadata sees them via Base.metadata."""

from src.infrastructure.persistence.models.agent_suggestion import AgentSuggestion
from src.infrastructure.persistence.models.currency import Currency
from src.infrastructure.persistence.models.document import Document
from src.infrastructure.persistence.models.feedback import Feedback
from src.infrastructure.persistence.models.format import Format
from src.infrastructure.persistence.models.order import Order
from src.infrastructure.persistence.models.order_line_item import OrderLineItem
from src.infrastructure.persistence.models.retailer import Retailer
from src.infrastructure.persistence.models.supplier import Supplier

__all__ = [
    "AgentSuggestion",
    "Currency",
    "Document",
    "Feedback",
    "Format",
    "Order",
    "OrderLineItem",
    "Retailer",
    "Supplier",
]
