"""Seed use case — wipes operational data and populates a realistic dataset.

Wipes (TRUNCATE CASCADE): feedbacks, agent_suggestions, order_line_items,
orders, documents. Reference data (currencies, formats) and accumulated
retailers/suppliers stay intact (suppliers/retailers are upserted from a
canonical list).

Uploads sample files via IngestOrderUseCase so they get a real Document row +
MinIO blob. Synthetic historical/pending orders skip MinIO (documents=[])
because we don't need 230 fake blobs.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.code_generation import generate_order_code
from src.application.ports.file_storage import FileStorage
from src.application.use_cases.ingest_order import IngestOrderInput, IngestOrderUseCase
from src.domain.enums import AgentAction, OperatorDecision, OrderStatus
from src.infrastructure.parsers.dispatcher import OrderParserDispatcher
from src.infrastructure.persistence.models.agent_suggestion import AgentSuggestion
from src.infrastructure.persistence.models.currency import Currency
from src.infrastructure.persistence.models.feedback import Feedback
from src.infrastructure.persistence.models.order import Order
from src.infrastructure.persistence.models.order_line_item import OrderLineItem
from src.infrastructure.persistence.models.retailer import Retailer
from src.infrastructure.persistence.models.supplier import Supplier

_log = logging.getLogger(__name__)


# Canonical seed data — matches the plan's retailer + supplier lists.
SEED_RETAILERS: list[tuple[str, str, str]] = [
    ("CARREFOUR-FR", "Carrefour France SA", "FR"),
    ("CARREFOUR-ES", "Carrefour España SA", "ES"),
    ("LEROY-ES", "Leroy Merlin España SA", "ES"),
    ("ELCORTE-ES", "El Corte Inglés SA", "ES"),
]

SEED_SUPPLIERS: list[tuple[str, str, str, str]] = [
    ("IBERIAN-FOODS", "Iberian Foods SL", "ES", "B12345678"),
    ("FASHION-PLUS", "Fashion Plus SL", "ES", "B23456789"),
    ("TOOLS-PLUS", "Tools Plus SA", "ES", "A34567890"),
    ("BODEGAS-RIOJA", "Bodegas Rioja SL", "ES", "B45678901"),
    ("EU-FASHION", "EU Fashion GmbH", "DE", "DE123456789"),
    ("ITALIAN-PASTA", "Italian Pasta Srl", "IT", "IT12345678901"),
    ("FRENCH-CHEESE", "French Cheese SARL", "FR", "FR12345678901"),
    ("MERCADONA-LOGI", "Mercadona Logística SL", "ES", "B56789012"),
]

# (sku, name, base_price_minor_units)
PRODUCT_CATALOG: list[tuple[str, str, int]] = [
    ("SKU-OIL-EVO-1L", "Extra Virgin Olive Oil 1L", 595),
    ("SKU-WINE-RIOJA-75CL", "Rioja Crianza 75cl", 795),
    ("SKU-HAM-IBERICO-200G", "Iberian Ham 200g", 1295),
    ("SKU-CHEESE-MAN-250G", "Manchego 250g", 875),
    ("SKU-PASTA-DURUM-500G", "Durum Pasta 500g", 195),
    ("SKU-COFFEE-BEANS-300G", "Coffee Beans 300g", 695),
    ("SKU-CHOC-DARK-100G", "Dark Chocolate 100g", 295),
    ("SKU-WATER-SPRING-1.5L", "Spring Water 1.5L", 75),
    ("SKU-TOOL-DRILL-18V", "Drill 18V", 8900),
    ("SKU-TOOL-HAMMER-500G", "Hammer 500g", 1295),
    ("SKU-SCREW-SET-100", "Screw Set 100pc", 495),
    ("SKU-SHIRT-COTTON-M", "Cotton Shirt M", 2995),
    ("SKU-JEANS-32X32", "Jeans 32x32", 4995),
    ("SKU-SHOES-LEATHER", "Leather Shoes Pair", 5995),
    ("SKU-BAG-LEATHER", "Leather Bag", 12995),
]

SAMPLE_FILES: list[str] = [
    "sample-json.json",
    "sample-xml-facturae.xml",
    "sample-csv.csv",
    "sample-edifact-carrefour.edi",
    # sample-pdf.pdf added at runtime if dispatcher includes a PDF parser.
]

# Synthetic Analyst Agent reasonings + matching anomaly lists.
SAMPLE_REASONINGS: list[tuple[str, list[str]]] = [
    ("Order matches recent purchasing pattern for this retailer-supplier pair.", []),
    ("Quantities and total amount are within historical range; no anomalies.", []),
    ("Standard SKUs ordered at standard quantities for this pair.", []),
    (
        "Order quantity is 2.3x higher than 90-day average; recommend review.",
        ["quantity_above_average"],
    ),
    (
        "New SKU not seen in last 50 orders for this pair — verify with supplier.",
        ["new_sku_unseen"],
    ),
    (
        "Unit price 15% above last 30 days; check for price change notification.",
        ["unit_price_outlier"],
    ),
    (
        "Total amount 3x typical; flagging for human review.",
        ["total_amount_3x_typical", "delivery_date_unusually_far"],
    ),
]


@dataclass(frozen=True)
class SeedResult:
    retailers_created: int
    suppliers_created: int
    samples_uploaded: int
    historical_orders_created: int
    pending_orders_created: int
    agent_suggestions_created: int
    feedbacks_created: int


class SeedUseCase:
    def __init__(
        self,
        session: AsyncSession,
        storage: FileStorage,
        dispatcher: OrderParserDispatcher,
        samples_dir: Path,
    ) -> None:
        self._session = session
        self._storage = storage
        self._dispatcher = dispatcher
        self._samples_dir = samples_dir

    async def execute(
        self,
        *,
        historical_count: int = 200,
        pending_count: int = 30,
        feedback_count: int = 50,
    ) -> SeedResult:
        await self._wipe()

        retailers = await self._upsert_retailers()
        suppliers = await self._upsert_suppliers()
        samples_uploaded = await self._upload_samples()
        currency = await self._get_eur_currency()

        historical = await self._generate_orders(
            retailers,
            suppliers,
            currency,
            count=historical_count,
            status=OrderStatus.APPROVED,
            date_window_days=90,
        )
        pending = await self._generate_orders(
            retailers,
            suppliers,
            currency,
            count=pending_count,
            status=OrderStatus.PENDING_REVIEW,
            date_window_days=7,
        )

        suggestions = await self._generate_suggestions(historical + pending)
        feedbacks_created = await self._generate_feedbacks(
            historical, suggestions, max_count=feedback_count
        )

        await self._session.commit()

        return SeedResult(
            retailers_created=len(retailers),
            suppliers_created=len(suppliers),
            samples_uploaded=samples_uploaded,
            historical_orders_created=len(historical),
            pending_orders_created=len(pending),
            agent_suggestions_created=len(suggestions),
            feedbacks_created=feedbacks_created,
        )

    # ---- Wipe ---------------------------------------------------------------

    async def _wipe(self) -> None:
        await self._session.execute(
            text(
                "TRUNCATE TABLE feedbacks, agent_suggestions, order_line_items, "
                "orders, documents CASCADE"
            )
        )
        await self._session.commit()

    # ---- Master data --------------------------------------------------------

    async def _upsert_retailers(self) -> list[Retailer]:
        result: list[Retailer] = []
        for code, name, country in SEED_RETAILERS:
            existing = (
                await self._session.execute(select(Retailer).where(Retailer.code == code))
            ).scalar_one_or_none()
            if existing is not None:
                result.append(existing)
                continue
            retailer = Retailer(id=uuid4(), code=code, name=name, country_code=country)
            self._session.add(retailer)
            await self._session.flush()
            result.append(retailer)
        return result

    async def _upsert_suppliers(self) -> list[Supplier]:
        result: list[Supplier] = []
        for code, name, country, tax_id in SEED_SUPPLIERS:
            existing = (
                await self._session.execute(select(Supplier).where(Supplier.code == code))
            ).scalar_one_or_none()
            if existing is not None:
                result.append(existing)
                continue
            supplier = Supplier(
                id=uuid4(), code=code, name=name, country_code=country, tax_id=tax_id
            )
            self._session.add(supplier)
            await self._session.flush()
            result.append(supplier)
        return result

    async def _get_eur_currency(self) -> Currency:
        return (
            await self._session.execute(select(Currency).where(Currency.code == "EUR"))
        ).scalar_one()

    # ---- Sample uploads (real ingestion) ------------------------------------

    async def _upload_samples(self) -> int:
        sample_files = list(SAMPLE_FILES)
        # Add PDF only when the dispatcher actually has a PDF parser registered.
        try:
            self._dispatcher.find_parser("dummy.pdf")
            sample_files.append("sample-pdf.pdf")
        except Exception:  # noqa: BLE001 — no PDF support is fine
            pass

        count = 0
        for filename in sample_files:
            path = self._samples_dir / filename
            if not path.exists():
                _log.warning("Sample file not found: %s", path)
                continue
            ingest = IngestOrderUseCase(
                session=self._session,
                storage=self._storage,
                dispatcher=self._dispatcher,
                broadcaster=None,  # Don't flood WS during a seed
            )
            try:
                await ingest.execute(
                    IngestOrderInput(file_bytes=path.read_bytes(), filename=filename)
                )
                count += 1
            except Exception as exc:  # noqa: BLE001
                _log.warning("Failed to ingest sample %s: %s", filename, exc)
        return count

    # ---- Synthetic orders ---------------------------------------------------

    async def _generate_orders(
        self,
        retailers: list[Retailer],
        suppliers: list[Supplier],
        currency: Currency,
        *,
        count: int,
        status: OrderStatus,
        date_window_days: int,
    ) -> list[Order]:
        orders: list[Order] = []
        now = datetime.now(UTC)
        for _ in range(count):
            retailer = random.choice(retailers)
            supplier = random.choice(suppliers)
            order_date = now - timedelta(
                days=random.randint(0, date_window_days),
                hours=random.randint(0, 23),
            )
            delivery_date = order_date + timedelta(days=random.randint(3, 14))

            line_count = random.randint(1, 5)
            chosen_products = random.sample(PRODUCT_CATALOG, line_count)
            total = 0
            order_id = uuid4()
            line_item_rows: list[OrderLineItem] = []
            for line_no, (sku, name, base_price) in enumerate(chosen_products, start=1):
                qty = random.randint(10, 200)
                unit_price = max(50, base_price + random.randint(-20, 20))
                line_total = qty * unit_price
                total += line_total
                line_item_rows.append(
                    OrderLineItem(
                        id=uuid4(),
                        order_id=order_id,
                        line_number=line_no,
                        product_code=sku,
                        product_name=name,
                        quantity=qty,
                        unit_price=unit_price,
                        line_total=line_total,
                    )
                )

            order = Order(
                id=order_id,
                code=generate_order_code(now=order_date),
                retailer_id=retailer.id,
                supplier_id=supplier.id,
                order_number=f"PO-{retailer.code}-{random.randint(100000, 999999):06d}",
                order_date=order_date,
                expected_delivery_date=delivery_date,
                status=status,
                total_amount=total,
                currency_id=currency.id,
                raw_payload={"source_format": "seed-generated"},
                documents=[],
            )
            self._session.add(order)
            for li in line_item_rows:
                self._session.add(li)
            orders.append(order)

        await self._session.flush()
        return orders

    # ---- Agent suggestions --------------------------------------------------

    async def _generate_suggestions(self, orders: list[Order]) -> list[AgentSuggestion]:
        suggestions: list[AgentSuggestion] = []
        for order in orders:
            reasoning, anomalies = random.choice(SAMPLE_REASONINGS)
            # Pending orders get evenly distributed actions; historical bias to approve.
            if order.status == OrderStatus.PENDING_REVIEW:
                action = random.choice(
                    [
                        AgentAction.APPROVE,
                        AgentAction.REQUEST_CLARIFICATION,
                        AgentAction.ESCALATE,
                    ]
                )
            else:
                action = random.choices(
                    [
                        AgentAction.APPROVE,
                        AgentAction.REQUEST_CLARIFICATION,
                        AgentAction.ESCALATE,
                    ],
                    weights=[8, 1, 1],
                )[0]

            confidence = Decimal(str(round(random.uniform(0.6, 0.99), 3)))

            suggestion = AgentSuggestion(
                id=uuid4(),
                order_id=order.id,
                agent_type="analyst",
                action=action,
                confidence=confidence,
                reasoning=reasoning,
                anomalies_detected=anomalies,
                phoenix_trace_id=None,
            )
            self._session.add(suggestion)
            suggestions.append(suggestion)
        await self._session.flush()
        return suggestions

    # ---- Feedbacks ----------------------------------------------------------

    async def _generate_feedbacks(
        self,
        historical: list[Order],
        suggestions: list[AgentSuggestion],
        *,
        max_count: int,
    ) -> int:
        suggestion_by_order = {s.order_id: s for s in suggestions}
        eligible = [o for o in historical if o.id in suggestion_by_order]
        chosen = random.sample(eligible, min(max_count, len(eligible)))

        for order in chosen:
            suggestion = suggestion_by_order[order.id]
            decision = random.choice(list(OperatorDecision))
            # If accepted, the operator concurred with the agent. Otherwise pick
            # a different action.
            if decision == OperatorDecision.ACCEPTED:
                final_action = suggestion.action
            else:
                others = [a for a in AgentAction if a != suggestion.action]
                final_action = random.choice(others)

            self._session.add(
                Feedback(
                    id=uuid4(),
                    order_id=order.id,
                    agent_suggestion_id=suggestion.id,
                    operator_decision=decision,
                    final_action=final_action,
                    operator_reason=f"Operator review: {decision.value}",
                    anomaly_feedback={},
                    phoenix_label_exported=False,
                )
            )
        await self._session.flush()
        return len(chosen)
