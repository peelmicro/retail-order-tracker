"""Human-readable codes — PREFIX-YYYY-MM-NNNNNN.

Suffix is derived from a UUID4 hex tail (6 uppercase chars) instead of a
true monthly sequence. A future iteration could back this with a
code_sequences table for guaranteed monotonicity, but for the demo this is
collision-resistant enough (16M-space per month) and avoids extra schema.
"""

from datetime import UTC, datetime
from uuid import uuid4


def _suffix() -> str:
    return uuid4().hex[:6].upper()


def _now() -> datetime:
    return datetime.now(UTC)


def generate_order_code(*, now: datetime | None = None) -> str:
    moment = now or _now()
    return f"ORD-{moment.year:04d}-{moment.month:02d}-{_suffix()}"


def generate_document_code(*, now: datetime | None = None) -> str:
    moment = now or _now()
    return f"DOC-{moment.year:04d}-{moment.month:02d}-{_suffix()}"
