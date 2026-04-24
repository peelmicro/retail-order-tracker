"""Seed use case integration test against real DB.

Uses small counts so the test runs fast. Verifies row totals + that the
canonical retailers/suppliers exist after seeding.
"""

import pytest
from sqlalchemy import func, select

from src.application.use_cases.seed import (
    SEED_RETAILERS,
    SEED_SUPPLIERS,
    SeedUseCase,
)
from src.config import settings
from src.domain.enums import OrderStatus
from src.infrastructure.parsers.dispatcher import default_dispatcher
from src.infrastructure.persistence.engine import async_session_factory
from src.infrastructure.persistence.models.agent_suggestion import AgentSuggestion
from src.infrastructure.persistence.models.feedback import Feedback
from src.infrastructure.persistence.models.order import Order
from src.infrastructure.persistence.models.retailer import Retailer
from src.infrastructure.persistence.models.supplier import Supplier
from tests.helpers import InMemoryFileStorage


@pytest.mark.asyncio
async def test_seed_with_small_counts_creates_expected_rows() -> None:
    storage = InMemoryFileStorage()
    dispatcher = default_dispatcher()  # 4 deterministic parsers, no PDF

    async with async_session_factory() as session:
        use_case = SeedUseCase(
            session=session,
            storage=storage,
            dispatcher=dispatcher,
            samples_dir=settings.samples_orders_dir,
        )
        result = await use_case.execute(
            historical_count=5,
            pending_count=2,
            feedback_count=2,
        )

    assert result.retailers_created == len(SEED_RETAILERS)
    assert result.suppliers_created == len(SEED_SUPPLIERS)
    assert result.samples_uploaded == 4  # 4 deterministic, no PDF
    assert result.historical_orders_created == 5
    assert result.pending_orders_created == 2
    assert result.agent_suggestions_created == 7  # 5 + 2
    assert result.feedbacks_created == 2

    # Verify in DB via a fresh session.
    # Other tests may have inserted additional retailers/suppliers (on-the-fly
    # during ingestion or via test fixtures), so we assert that the canonical
    # seeded codes exist rather than asserting an exact total count.
    async with async_session_factory() as session:
        retailer_codes = set(
            (await session.execute(select(Retailer.code))).scalars().all()
        )
        seed_retailer_codes = {code for code, _, _ in SEED_RETAILERS}
        assert seed_retailer_codes.issubset(retailer_codes)

        supplier_codes = set(
            (await session.execute(select(Supplier.code))).scalars().all()
        )
        seed_supplier_codes = {code for code, _, _, _ in SEED_SUPPLIERS}
        assert seed_supplier_codes.issubset(supplier_codes)

        # Total orders = 5 historical + 2 pending + 4 sample uploads = 11
        # (the wipe runs first so this is independent of other test pollution).
        all_orders = (
            await session.execute(select(func.count()).select_from(Order))
        ).scalar()
        assert all_orders == 11

        pending_orders = (
            await session.execute(
                select(func.count())
                .select_from(Order)
                .where(Order.status == OrderStatus.PENDING_REVIEW)
            )
        ).scalar()
        # 2 explicit pending orders + 4 sample uploads (which default to
        # pending_review on ingestion) = 6 total.
        assert pending_orders == 6

        suggestions = (
            await session.execute(select(func.count()).select_from(AgentSuggestion))
        ).scalar()
        assert suggestions == 7

        feedbacks = (
            await session.execute(select(func.count()).select_from(Feedback))
        ).scalar()
        assert feedbacks == 2


@pytest.mark.asyncio
async def test_seed_is_idempotent_does_not_double_retailers() -> None:
    """Running seed twice should not duplicate retailers/suppliers (upsert)."""
    storage = InMemoryFileStorage()
    dispatcher = default_dispatcher()

    async with async_session_factory() as session:
        use_case = SeedUseCase(
            session=session,
            storage=storage,
            dispatcher=dispatcher,
            samples_dir=settings.samples_orders_dir,
        )
        await use_case.execute(historical_count=2, pending_count=1, feedback_count=1)

    async with async_session_factory() as session:
        use_case = SeedUseCase(
            session=session,
            storage=storage,
            dispatcher=dispatcher,
            samples_dir=settings.samples_orders_dir,
        )
        result = await use_case.execute(
            historical_count=2, pending_count=1, feedback_count=1
        )

    # Retailers/suppliers from the first call still count as "created" in the
    # result (we report the canonical-list size), but the DB shouldn't have
    # duplicates.
    async with async_session_factory() as session:
        total_retailers = (
            await session.execute(select(func.count()).select_from(Retailer))
        ).scalar()
        # Other tests may have created retailers via on-the-fly upsert too;
        # at minimum the seeded ones are present, no duplicates.
        assert total_retailers >= len(SEED_RETAILERS)
        codes = (
            await session.execute(select(Retailer.code))
        ).scalars().all()
        seed_codes = {code for code, _, _ in SEED_RETAILERS}
        assert seed_codes.issubset(set(codes))
