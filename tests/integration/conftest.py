import os

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.models import Base

# Integration tests require a real PostgreSQL instance.
# Set TEST_DATABASE_URL env var to override the default.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://tgbot:tgbot@localhost:5432/tgbot_test",
)


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session(test_engine) -> AsyncSession:
    """
    Provide a session that is rolled back after each test (no persistent state).
    """
    async_session = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with test_engine.begin() as conn:
        # Use a savepoint so we can rollback after each test
        async with async_session(bind=conn) as sess:
            await conn.begin_nested()
            yield sess
            await conn.rollback()
