import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Hashtag
from src.db.repository import (
    create_hashtag,
    delete_hashtag,
    get_hashtag_by_tag,
    list_hashtags,
)

logger = logging.getLogger(__name__)


async def add_hashtag(
    session: AsyncSession,
    tag: str,
    created_by: int,
    description: str | None = None,
) -> tuple[Hashtag, bool]:
    """
    Create a hashtag. Returns (hashtag, created).
    created=False if hashtag already exists.
    """
    logger.info("add_hashtag: tag=%r created_by=%d", tag, created_by)

    # Normalize tag: strip # — tags are stored without # in the DB
    tag = tag.lstrip("#").strip()

    existing = await get_hashtag_by_tag(session, tag)
    if existing is not None:
        logger.warning("add_hashtag: tag=%r already exists", tag)
        return existing, False

    hashtag = await create_hashtag(session, tag=tag, created_by=created_by, description=description)
    return hashtag, True


async def remove_hashtag(session: AsyncSession, tag: str) -> bool:
    """Delete a hashtag by tag string. Returns True if deleted."""
    logger.info("remove_hashtag: tag=%r", tag)
    tag = tag.lstrip("#").strip()
    return await delete_hashtag(session, tag)


async def get_all_hashtags(session: AsyncSession) -> list[Hashtag]:
    logger.debug("get_all_hashtags: fetching all")
    return await list_hashtags(session)
