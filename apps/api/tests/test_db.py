import pytest
from sqlalchemy import text

from src.infrastructure.persistence.engine import engine

EXPECTED_TABLES = {
    "currencies",
    "formats",
    "documents",
    "retailers",
    "suppliers",
    "orders",
    "order_line_items",
    "agent_suggestions",
    "feedbacks",
}


@pytest.mark.asyncio
async def test_all_expected_tables_exist() -> None:
    """Verifies the initial Alembic migration has been applied.

    Run `npm run api:migrate` first if this test fails on a fresh database.
    """
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        )
        actual = {row[0] for row in result}

    missing = EXPECTED_TABLES - actual
    assert not missing, f"Missing tables: {missing}. Did you run `npm run api:migrate`?"


@pytest.mark.asyncio
async def test_expected_enums_exist() -> None:
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT typname FROM pg_type WHERE typtype = 'e'"))
        actual = {row[0] for row in result}

    expected = {"order_status", "agent_action", "operator_decision"}
    missing = expected - actual
    assert not missing, f"Missing enum types: {missing}"
