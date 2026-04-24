"""Integration tests for IngestOrderUseCase against the real DB.

Requires migrations 0001 and 0002 applied (`npm run api:migrate`). Uses the
in-memory FileStorage fake so MinIO is not exercised here — the MinIO adapter
is covered separately by tests/storage/.
"""

from pathlib import Path

import pytest
from sqlalchemy import select

from src.application.exceptions import UnknownCurrencyError
from src.application.use_cases.ingest_order import IngestOrderInput, IngestOrderUseCase
from src.domain.enums import OrderStatus
from src.infrastructure.parsers.dispatcher import default_dispatcher
from src.infrastructure.persistence.engine import async_session_factory
from src.infrastructure.persistence.models.document import Document
from src.infrastructure.persistence.models.order import Order
from src.infrastructure.persistence.models.order_line_item import OrderLineItem
from tests.helpers import InMemoryFileStorage

SAMPLES_DIR = Path(__file__).resolve().parents[4] / "samples" / "orders"


@pytest.fixture
def storage() -> InMemoryFileStorage:
    return InMemoryFileStorage()


@pytest.fixture
def dispatcher():
    return default_dispatcher()


async def _run(storage, dispatcher, filename: str, mime_type: str | None = None):
    file_bytes = (SAMPLES_DIR / filename).read_bytes()
    async with async_session_factory() as session:
        use_case = IngestOrderUseCase(session=session, storage=storage, dispatcher=dispatcher)
        result = await use_case.execute(
            IngestOrderInput(file_bytes=file_bytes, filename=filename, mime_type=mime_type)
        )
    return result, file_bytes


@pytest.mark.asyncio
async def test_ingests_json_order_persists_db_rows_and_uploads_blob(
    storage, dispatcher
) -> None:
    result, file_bytes = await _run(storage, dispatcher, "sample-json.json", "application/json")

    # Result shape
    assert result.order_code.startswith("ORD-2026-")
    assert result.storage_path == f"orders/{result.order_id}/sample-json.json"
    assert result.parsed_order.order_number == "PO-CARREFOUR-000123"
    assert result.parsed_order.total_amount == 124_250

    # MinIO fake received the original bytes
    assert storage.store[result.storage_path][0] == file_bytes
    assert storage.store[result.storage_path][1] == "application/json"

    # DB rows
    async with async_session_factory() as session:
        order = (
            await session.execute(select(Order).where(Order.id == result.order_id))
        ).scalar_one()
        assert order.code == result.order_code
        assert order.status == OrderStatus.PENDING_REVIEW
        assert order.total_amount == 124_250
        assert order.documents == [str(result.document_id)]

        document = (
            await session.execute(
                select(Document).where(Document.id == result.document_id)
            )
        ).scalar_one()
        assert document.storage_path == result.storage_path

        line_items = (
            await session.execute(
                select(OrderLineItem).where(OrderLineItem.order_id == result.order_id)
            )
        ).scalars().all()
        assert len(line_items) == 2


@pytest.mark.asyncio
async def test_ingests_xml_order(storage, dispatcher) -> None:
    result, _ = await _run(storage, dispatcher, "sample-xml-facturae.xml", "application/xml")
    assert result.parsed_order.order_number == "PO-ELCORTE-000789"
    assert result.parsed_order.total_amount == 299_600


@pytest.mark.asyncio
async def test_ingests_csv_order(storage, dispatcher) -> None:
    result, _ = await _run(storage, dispatcher, "sample-csv.csv", "text/csv")
    assert result.parsed_order.order_number == "PO-LEROY-000456"
    assert len(result.parsed_order.line_items) == 3


@pytest.mark.asyncio
async def test_ingests_edifact_order(storage, dispatcher) -> None:
    result, _ = await _run(storage, dispatcher, "sample-edifact-carrefour.edi")
    assert result.parsed_order.order_number == "PO-CARREFOUR-000321"
    assert result.parsed_order.total_amount == 254_000


@pytest.mark.asyncio
async def test_unsupported_format_raises(storage, dispatcher) -> None:
    from src.application.ports.order_parser import UnsupportedFormatError

    async with async_session_factory() as session:
        use_case = IngestOrderUseCase(session=session, storage=storage, dispatcher=dispatcher)
        with pytest.raises(UnsupportedFormatError):
            await use_case.execute(
                IngestOrderInput(
                    file_bytes=b"random bytes",
                    filename="order.txt",
                )
            )

    # No MinIO write should have happened
    assert storage.store == {}


@pytest.mark.asyncio
async def test_unknown_currency_raises(storage, dispatcher, monkeypatch) -> None:
    """Force the parser to produce an unknown currency code by patching the
    JSON parser's output. Verifies the use case rejects it cleanly."""
    from src.application.dtos import OrderDTO
    from src.infrastructure.parsers import json_parser

    real_parse = json_parser.JsonOrderParser.parse

    def fake_parse(self, file_bytes, filename):
        order = real_parse(self, file_bytes, filename)
        return OrderDTO.model_validate({**order.model_dump(), "currencyCode": "ZZZ"})

    monkeypatch.setattr(json_parser.JsonOrderParser, "parse", fake_parse)

    async with async_session_factory() as session:
        use_case = IngestOrderUseCase(session=session, storage=storage, dispatcher=dispatcher)
        with pytest.raises(UnknownCurrencyError):
            file_bytes = (SAMPLES_DIR / "sample-json.json").read_bytes()
            await use_case.execute(
                IngestOrderInput(
                    file_bytes=file_bytes,
                    filename="sample-json.json",
                    mime_type="application/json",
                )
            )
