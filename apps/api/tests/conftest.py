import pytest_asyncio

from src.infrastructure.persistence.engine import engine


@pytest_asyncio.fixture(autouse=True)
async def _dispose_engine_between_tests():
    """Each test gets its own event loop, but our engine is a module-level
    singleton with a connection pool. Disposing after every test forces the
    pool to close so the next test can create fresh connections bound to its
    own loop — fixes 'Future attached to a different loop' errors."""
    yield
    await engine.dispose()
