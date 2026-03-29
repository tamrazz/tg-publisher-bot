import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ContentType, Hashtag, Post, PostHashtag, PostStatus, User, UserRole

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------


async def get_user(session: AsyncSession, telegram_id: int) -> User | None:
    logger.debug("get_user: telegram_id=%d", telegram_id)
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None,
    role: UserRole = UserRole.admin,
) -> tuple[User, bool]:
    """Return (user, created). created=True if a new row was inserted."""
    logger.debug(
        "get_or_create_user: telegram_id=%d username=%r role=%s",
        telegram_id,
        username,
        role,
    )
    user = await get_user(session, telegram_id)
    if user is not None:
        logger.debug("get_or_create_user: existing user found")
        return user, False

    user = User(telegram_id=telegram_id, username=username, role=role)
    session.add(user)
    await session.flush()
    logger.info("get_or_create_user: created new user telegram_id=%d role=%s", telegram_id, role)
    return user, True


async def update_user_role(session: AsyncSession, telegram_id: int, role: UserRole) -> User | None:
    logger.debug("update_user_role: telegram_id=%d → role=%s", telegram_id, role)
    user = await get_user(session, telegram_id)
    if user is None:
        logger.warning("update_user_role: user not found telegram_id=%d", telegram_id)
        return None
    user.role = role
    await session.flush()
    logger.info("update_user_role: updated telegram_id=%d to role=%s", telegram_id, role)
    return user


async def delete_user(session: AsyncSession, telegram_id: int) -> bool:
    logger.debug("delete_user: telegram_id=%d", telegram_id)
    user = await get_user(session, telegram_id)
    if user is None:
        logger.warning("delete_user: user not found telegram_id=%d", telegram_id)
        return False
    await session.delete(user)
    await session.flush()
    logger.info("delete_user: deleted telegram_id=%d", telegram_id)
    return True


# ---------------------------------------------------------------------------
# Post CRUD
# ---------------------------------------------------------------------------


async def is_url_processed(session: AsyncSession, url: str) -> bool:
    """Return True if a Post with this URL exists (deduplication check)."""
    logger.debug("is_url_processed: url=%r", url)
    result = await session.execute(select(Post.id).where(Post.url == url))
    exists = result.scalar_one_or_none() is not None
    logger.debug("is_url_processed: url=%r → %s", url, exists)
    return exists


async def create_post(
    session: AsyncSession,
    url: str,
    content_type: ContentType,
    created_by: int,
    raw_content: str | None = None,
    post_text: str | None = None,
    status: PostStatus = PostStatus.pending,
) -> Post:
    logger.debug(
        "create_post: url=%r content_type=%s created_by=%d status=%s",
        url,
        content_type,
        created_by,
        status,
    )
    post = Post(
        url=url,
        content_type=content_type,
        created_by=created_by,
        raw_content=raw_content,
        post_text=post_text,
        status=status,
    )
    session.add(post)
    await session.flush()
    logger.info("create_post: created post id=%d url=%r", post.id, url)
    return post


async def get_post(session: AsyncSession, post_id: int) -> Post | None:
    logger.debug("get_post: post_id=%d", post_id)
    result = await session.execute(select(Post).where(Post.id == post_id))
    return result.scalar_one_or_none()


async def get_post_by_url(session: AsyncSession, url: str) -> Post | None:
    logger.debug("get_post_by_url: url=%r", url)
    result = await session.execute(select(Post).where(Post.url == url))
    return result.scalar_one_or_none()


async def update_post_status(
    session: AsyncSession, post_id: int, status: PostStatus
) -> Post | None:
    logger.debug("update_post_status: post_id=%d → status=%s", post_id, status)
    post = await get_post(session, post_id)
    if post is None:
        logger.warning("update_post_status: post not found post_id=%d", post_id)
        return None
    post.status = status
    if status == PostStatus.published:
        post.published_at = datetime.now(UTC)
    await session.flush()
    logger.info("update_post_status: post id=%d → status=%s", post_id, status)
    return post


async def update_post_text(session: AsyncSession, post_id: int, post_text: str) -> Post | None:
    logger.debug("update_post_text: post_id=%d", post_id)
    post = await get_post(session, post_id)
    if post is None:
        logger.warning("update_post_text: post not found post_id=%d", post_id)
        return None
    post.post_text = post_text
    await session.flush()
    logger.debug("update_post_text: updated post id=%d", post_id)
    return post


# ---------------------------------------------------------------------------
# Hashtag CRUD
# ---------------------------------------------------------------------------


async def create_hashtag(
    session: AsyncSession,
    tag: str,
    created_by: int,
    description: str | None = None,
) -> Hashtag:
    logger.debug("create_hashtag: tag=%r created_by=%d", tag, created_by)
    hashtag = Hashtag(tag=tag, description=description, created_by=created_by)
    session.add(hashtag)
    await session.flush()
    logger.info("create_hashtag: created hashtag id=%d tag=%r", hashtag.id, tag)
    return hashtag


async def get_hashtag_by_tag(session: AsyncSession, tag: str) -> Hashtag | None:
    logger.debug("get_hashtag_by_tag: tag=%r", tag)
    result = await session.execute(select(Hashtag).where(Hashtag.tag == tag))
    return result.scalar_one_or_none()


async def list_hashtags(session: AsyncSession) -> list[Hashtag]:
    logger.debug("list_hashtags: fetching all hashtags")
    result = await session.execute(select(Hashtag).order_by(Hashtag.tag))
    hashtags = list(result.scalars().all())
    logger.debug("list_hashtags: found %d hashtags", len(hashtags))
    return hashtags


async def delete_hashtag(session: AsyncSession, tag: str) -> bool:
    logger.debug("delete_hashtag: tag=%r", tag)
    hashtag = await get_hashtag_by_tag(session, tag)
    if hashtag is None:
        logger.warning("delete_hashtag: hashtag not found tag=%r", tag)
        return False
    await session.delete(hashtag)
    await session.flush()
    logger.info("delete_hashtag: deleted tag=%r", tag)
    return True


# ---------------------------------------------------------------------------
# PostHashtag
# ---------------------------------------------------------------------------


async def attach_hashtags_to_post(
    session: AsyncSession, post_id: int, hashtag_ids: list[int]
) -> None:
    logger.debug("attach_hashtags_to_post: post_id=%d hashtag_ids=%s", post_id, hashtag_ids)
    for hashtag_id in hashtag_ids:
        ph = PostHashtag(post_id=post_id, hashtag_id=hashtag_id)
        session.add(ph)
    await session.flush()
    logger.debug(
        "attach_hashtags_to_post: attached %d hashtags to post_id=%d",
        len(hashtag_ids),
        post_id,
    )
