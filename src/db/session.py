import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    echo=settings.log_level == "DEBUG",
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Yield an async SQLAlchemy session."""
    logger.debug("Opening new DB session")
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
            logger.debug("DB session committed")
        except Exception:
            await session.rollback()
            logger.debug("DB session rolled back")
            raise
        finally:
            logger.debug("DB session closed")
