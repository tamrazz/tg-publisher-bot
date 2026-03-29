import logging
from dataclasses import dataclass

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.composer import compose_post
from src.ai.hashtag_matcher import match_hashtags
from src.ai.summarizer import summarize
from src.db.models import ContentType, Post, PostStatus
from src.db.repository import (
    attach_hashtags_to_post,
    create_post,
    get_hashtag_by_tag,
    get_post_by_url,
    is_url_processed,
    list_hashtags,
    update_post_status,
    update_post_text,
)
from src.extractors.base import get_extractor
from src.extractors.detector import detect_content_type
from src.publisher.channel import publish_to_channel

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    post: Post
    post_text: str
    published: bool
    already_exists: bool


async def process_url(
    *,
    url: str,
    created_by: int,
    session: AsyncSession,
    bot: Bot,
    moderate: bool = True,
    force: bool = False,
) -> PipelineResult:
    """
    Full pipeline: detect → extract → summarize → match hashtags → compose
    → save to DB → optionally publish.

    If *moderate* is True, the post is saved as pending (admin must approve).
    If *moderate* is False, the post is published immediately.
    If *force* is True, skip the deduplication check and reprocess the URL.
    """
    logger.info(
        "process_url: url=%r created_by=%d moderate=%s force=%s",
        url,
        created_by,
        moderate,
        force,
    )

    # --- Deduplication check ---
    if not force and await is_url_processed(session, url):
        logger.warning("process_url: url already processed url=%r", url)
        existing_post = await _get_existing_post(session, url)
        return PipelineResult(
            post=existing_post,
            post_text=existing_post.post_text or "",
            published=False,
            already_exists=True,
        )

    # --- Detect content type ---
    content_type = detect_content_type(url)
    logger.info("process_url: detected content_type=%s url=%r", content_type, url)

    # --- Extract content ---
    extractor = get_extractor(content_type)
    logger.debug("process_url: running extractor=%s url=%r", type(extractor).__name__, url)
    try:
        extracted = await extractor.extract(url)
        logger.info(
            "process_url: extraction done title=%r author=%r text_len=%d",
            extracted.title,
            extracted.author,
            len(extracted.text),
        )
    except Exception as exc:
        logger.warning(
            "[FIX] process_url: extraction failed, falling back to URL-only post url=%r error=%s",
            url,
            exc,
        )
        extracted = None

    # --- AI Summarization ---
    if extracted is None:
        announcement = None
        matched_tags = []
    else:
        logger.debug("process_url: running summarizer")
        announcement = await summarize(extracted)

    if announcement is None:
        # No AI provider or extraction failed — publish URL only without hashtags
        logger.warning(
            "[FIX] process_url: AI unavailable or extraction failed, composing URL-only post url=%r", url
        )
        matched_tags = []
    else:
        logger.debug("process_url: announcement_len=%d", len(announcement))
        # --- Hashtag matching ---
        logger.debug("process_url: fetching available hashtags from DB")
        hashtag_rows = await list_hashtags(session)
        available_tags = [row.tag for row in hashtag_rows]
        logger.debug("process_url: available_tags_count=%d", len(available_tags))
        matched_tags = await match_hashtags(announcement, available_tags)
        logger.info("process_url: matched_tags=%s", matched_tags)

    # --- Compose final post ---
    post_text = compose_post(
        announcement=announcement,
        source_url=url,
        hashtags=matched_tags,
    )
    logger.debug("process_url: composed post_text_len=%d", len(post_text))

    # --- Save to DB ---
    status = PostStatus.pending if moderate else PostStatus.published
    existing_for_force = await get_post_by_url(session, url) if force else None
    if existing_for_force is not None:
        # force=True and URL exists: update in-place to avoid UNIQUE constraint violation
        logger.info(
            "[FIX] process_url: force=True, updating existing post id=%d url=%r",
            existing_for_force.id,
            url,
        )
        existing_for_force.raw_content = extracted.text if extracted is not None else ""
        existing_for_force.post_text = post_text
        existing_for_force.status = status
        existing_for_force.content_type = ContentType(content_type.value)
        await session.flush()
        post = existing_for_force
    else:
        post = await create_post(
            session=session,
            url=url,
            content_type=ContentType(content_type.value),
            created_by=created_by,
            raw_content=extracted.text if extracted is not None else "",
            post_text=post_text,
            status=status,
        )
    logger.info("[FIX] process_url: saved post id=%d status=%s force=%s", post.id, status, force)

    # --- Attach hashtags ---
    if matched_tags:
        hashtag_ids = []
        for tag in matched_tags:
            row = await get_hashtag_by_tag(session, tag)
            if row:
                hashtag_ids.append(row.id)
        if hashtag_ids:
            await attach_hashtags_to_post(session, post.id, hashtag_ids)
            logger.debug(
                "process_url: attached hashtag_ids=%s to post_id=%d",
                hashtag_ids,
                post.id,
            )

    # --- Publish immediately if not moderated ---
    published = False
    if not moderate:
        logger.info("process_url: publishing immediately post_id=%d", post.id)
        await publish_to_channel(bot, post_text)
        await update_post_status(session, post.id, PostStatus.published)
        published = True
        logger.info("process_url: published post_id=%d", post.id)

    return PipelineResult(
        post=post,
        post_text=post_text,
        published=published,
        already_exists=False,
    )


async def regenerate_announcement(
    *,
    post_id: int,
    session: AsyncSession,
) -> tuple[Post, str] | None:
    """
    Re-generate the announcement for an existing post using its cached raw_content.
    Skips extraction/transcription entirely — only re-runs summarizer + hashtag matching.
    Returns (post, new_post_text) or None if post not found.
    """
    logger.info("[FIX] regenerate_announcement: post_id=%d", post_id)

    from src.db.repository import get_post

    post = await get_post(session, post_id)
    if post is None:
        logger.warning("[FIX] regenerate_announcement: post not found post_id=%d", post_id)
        return None

    raw = post.raw_content or ""
    logger.debug(
        "[FIX] regenerate_announcement: raw_content_len=%d post_id=%d", len(raw), post_id
    )

    if raw:
        from src.extractors.base import ExtractedContent
        from src.extractors.detector import ContentType as DetectorContentType

        extracted = ExtractedContent(
            text=raw,
            title=None,
            author=None,
            source_url=post.url,
            content_type=DetectorContentType(post.content_type.value),
        )
        announcement = await summarize(extracted)
        logger.debug(
            "[FIX] regenerate_announcement: announcement_len=%d post_id=%d",
            len(announcement) if announcement else 0,
            post_id,
        )
    else:
        announcement = None
        logger.warning(
            "[FIX] regenerate_announcement: no raw_content, composing URL-only post_id=%d",
            post_id,
        )

    if announcement is not None:
        hashtag_rows = await list_hashtags(session)
        available_tags = [row.tag for row in hashtag_rows]
        matched_tags = await match_hashtags(announcement, available_tags)
        logger.info(
            "[FIX] regenerate_announcement: matched_tags=%s post_id=%d", matched_tags, post_id
        )
    else:
        matched_tags = []

    post_text = compose_post(
        announcement=announcement,
        source_url=post.url,
        hashtags=matched_tags,
    )

    post = await update_post_text(session, post_id, post_text)
    logger.info("[FIX] regenerate_announcement: updated post_text post_id=%d", post_id)
    return post, post_text


async def publish_pending_post(
    *,
    post_id: int,
    edited_text: str | None = None,
    session: AsyncSession,
    bot: Bot,
) -> Post | None:
    """
    Publish a pending post (from moderation queue).
    Optionally update post_text if admin edited it.
    """
    logger.info("publish_pending_post: post_id=%d edited=%s", post_id, edited_text is not None)

    from src.db.repository import get_post

    post = await get_post(session, post_id)
    if post is None:
        logger.warning("publish_pending_post: post not found post_id=%d", post_id)
        return None

    if post.status != PostStatus.pending:
        logger.warning(
            "publish_pending_post: post_id=%d is not pending (status=%s)",
            post_id,
            post.status,
        )
        return None

    if edited_text is not None:
        post = await update_post_text(session, post_id, edited_text)
        logger.info("publish_pending_post: post text updated post_id=%d", post_id)

    final_text = post.post_text or ""
    logger.debug(
        "publish_pending_post: publishing post_id=%d text_len=%d", post_id, len(final_text)
    )
    await publish_to_channel(bot, final_text)
    await update_post_status(session, post_id, PostStatus.published)
    logger.info("publish_pending_post: published post_id=%d", post_id)
    return post


async def reject_post(*, post_id: int, session: AsyncSession) -> Post | None:
    """Mark a pending post as rejected."""
    logger.info("reject_post: post_id=%d", post_id)

    from src.db.repository import get_post

    post = await get_post(session, post_id)
    if post is None:
        logger.warning("reject_post: post not found post_id=%d", post_id)
        return None

    await update_post_status(session, post_id, PostStatus.rejected)
    logger.info("reject_post: rejected post_id=%d", post_id)
    return post


async def _get_existing_post(session: AsyncSession, url: str) -> Post:
    """Helper: fetch an existing post by URL (guaranteed to exist after dedup check)."""
    from src.db.repository import get_post_by_url

    post = await get_post_by_url(session, url)
    assert post is not None, f"Expected post to exist for url={url!r}"
    return post
