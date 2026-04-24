"""Order ingestion use case — single transaction binding parse + storage + DB.

Order of side effects (deliberate):
  1. Parse the file. Failures here = no MinIO write, no DB row, clean 4xx.
  2. Upload the original bytes to MinIO under orders/{order_id}/{filename}.
  3. Insert document + order + line_items rows in one DB transaction.

If the DB transaction fails after the MinIO upload, the blob becomes an
orphan. Acceptable trade-off: keeping MinIO and DB in a true 2-phase commit
would add significant complexity for a tiny consistency window. A future
async cleanup job could sweep blobs without a matching document row.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.code_generation import generate_document_code, generate_order_code
from src.application.dtos import OrderDTO
from src.application.exceptions import UnknownCurrencyError, UnknownFormatError
from src.application.ports.event_broadcaster import EventBroadcaster, OrderCreatedEvent
from src.application.ports.file_storage import FileStorage
from src.domain.enums import OrderStatus
from src.infrastructure.parsers.dispatcher import OrderParserDispatcher
from src.infrastructure.persistence.models.currency import Currency
from src.infrastructure.persistence.models.document import Document
from src.infrastructure.persistence.models.format import Format
from src.infrastructure.persistence.models.order import Order
from src.infrastructure.persistence.models.order_line_item import OrderLineItem
from src.infrastructure.persistence.models.retailer import Retailer
from src.infrastructure.persistence.models.supplier import Supplier

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestOrderInput:
    file_bytes: bytes
    filename: str
    mime_type: str | None = None


@dataclass(frozen=True)
class IngestOrderResult:
    order_id: UUID
    order_code: str
    document_id: UUID
    storage_path: str
    parsed_order: OrderDTO


class IngestOrderUseCase:
    def __init__(
        self,
        session: AsyncSession,
        storage: FileStorage,
        dispatcher: OrderParserDispatcher,
        broadcaster: EventBroadcaster | None = None,
    ) -> None:
        self._session = session
        self._storage = storage
        self._dispatcher = dispatcher
        self._broadcaster = broadcaster

    async def execute(self, input: IngestOrderInput) -> IngestOrderResult:
        # 1. Parse first — UnsupportedFormatError raised here aborts cleanly.
        parser = self._dispatcher.find_parser(input.filename, input.mime_type)
        parsed = parser.parse(input.file_bytes, input.filename)
        format_code = parser.name

        # 2. Allocate IDs + codes ahead of MinIO upload so the storage path is
        #    deterministic from order_id and we never need to rename later.
        order_id = uuid4()
        order_code = generate_order_code()
        document_id = uuid4()
        document_code = generate_document_code()
        storage_path = f"orders/{order_id}/{input.filename}"

        # 3. Upload to MinIO. Failures abort here, no DB writes attempted.
        self._storage.upload(
            storage_path,
            input.file_bytes,
            content_type=input.mime_type,
        )

        # 4. DB transaction — all-or-nothing.
        format_id = await self._lookup_format_id(format_code)
        retailer_id = await self._upsert_retailer(parsed.retailer_code, parsed.retailer_name)
        supplier_id = await self._upsert_supplier(parsed.supplier_code, parsed.supplier_name)
        currency_id = await self._lookup_currency_id(parsed.currency_code)

        document = Document(
            id=document_id,
            code=document_code,
            filename=input.filename,
            storage_path=storage_path,
            format_id=format_id,
        )
        self._session.add(document)

        order = Order(
            id=order_id,
            code=order_code,
            retailer_id=retailer_id,
            supplier_id=supplier_id,
            order_number=parsed.order_number,
            order_date=parsed.order_date,
            expected_delivery_date=parsed.expected_delivery_date,
            status=OrderStatus.PENDING_REVIEW,
            total_amount=parsed.total_amount,
            currency_id=currency_id,
            raw_payload=parsed.model_dump(mode="json", by_alias=True),
            documents=[str(document_id)],
        )
        self._session.add(order)

        for line in parsed.line_items:
            self._session.add(
                OrderLineItem(
                    id=uuid4(),
                    order_id=order_id,
                    line_number=line.line_number,
                    product_code=line.product_code,
                    product_name=line.product_name,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    line_total=line.line_total,
                )
            )

        await self._session.commit()

        # Best-effort broadcast — failures must not roll back the order.
        if self._broadcaster is not None:
            try:
                await self._broadcaster.broadcast(
                    OrderCreatedEvent(
                        order_id=order_id,
                        order_code=order_code,
                        retailer_code=parsed.retailer_code,
                        retailer_name=parsed.retailer_name,
                        supplier_code=parsed.supplier_code,
                        supplier_name=parsed.supplier_name,
                        currency_code=parsed.currency_code,
                        total_amount=parsed.total_amount,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                _log.warning("Order broadcast failed: %s", exc)

        return IngestOrderResult(
            order_id=order_id,
            order_code=order_code,
            document_id=document_id,
            storage_path=storage_path,
            parsed_order=parsed,
        )

    # --- DB helpers ----------------------------------------------------------

    async def _lookup_format_id(self, code: str) -> UUID:
        result = await self._session.execute(select(Format).where(Format.code == code))
        fmt = result.scalar_one_or_none()
        if fmt is None:
            raise UnknownFormatError(code)
        return fmt.id

    async def _lookup_currency_id(self, code: str) -> UUID:
        result = await self._session.execute(select(Currency).where(Currency.code == code))
        currency = result.scalar_one_or_none()
        if currency is None:
            raise UnknownCurrencyError(code)
        return currency.id

    async def _upsert_retailer(self, code: str, name: str) -> UUID:
        result = await self._session.execute(select(Retailer).where(Retailer.code == code))
        retailer = result.scalar_one_or_none()
        if retailer is not None:
            return retailer.id
        retailer = Retailer(id=uuid4(), code=code, name=name)
        self._session.add(retailer)
        await self._session.flush()
        return retailer.id

    async def _upsert_supplier(self, code: str, name: str) -> UUID:
        result = await self._session.execute(select(Supplier).where(Supplier.code == code))
        supplier = result.scalar_one_or_none()
        if supplier is not None:
            return supplier.id
        supplier = Supplier(id=uuid4(), code=code, name=name)
        self._session.add(supplier)
        await self._session.flush()
        return supplier.id
