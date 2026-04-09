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

    Uses join_transaction_mode="create_savepoint" so that any session.commit()
    calls inside tests create a SAVEPOINT instead of committing the outer
    transaction, which is rolled back unconditionally after each test.
    """
    async with test_engine.connect() as conn:
        await conn.begin()
        async_session = async_sessionmaker(
            bind=conn,
            class_=AsyncSession,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        async with async_session() as sess:
            yield sess
        await conn.rollback()
