import logging
from dataclasses import dataclass

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.composer import compose_post
from src.ai.hashtag_generator import generate_extra_hashtags
from src.ai.hashtag_matcher import match_hashtags
from src.ai.summarizer import summarize
from src.db.models import ContentType, Post, PostStatus
from src.db.repository import (
    attach_hashtags_to_post,
    create_hashtag,
    create_post,
    get_category_by_name,
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
            "[FIX] process_url: AI unavailable or extraction failed, "
            "composing URL-only post url=%r",
            url,
        )
        matched_tags = []
    else:
        logger.debug("process_url: announcement_len=%d", len(announcement))
        # --- Hashtag matching ---
        logger.debug("process_url: fetching available hashtags from DB")
        hashtag_rows = await list_hashtags(session)
        logger.debug("process_url: available_hashtags_count=%d", len(hashtag_rows))
        matched_tags = await match_hashtags(announcement, hashtag_rows)
        raw_match_count = len(matched_tags)
        matched_tags = _sort_and_limit_hashtags(matched_tags, hashtag_rows)
        logger.info(
            "[pipeline] process_url: hashtags matched=%d final=%d",
            raw_match_count,
            len(matched_tags),
        )
        matched_tags = await _fill_with_generated_hashtags(
            announcement, matched_tags, session=session, created_by=created_by
        )

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
        hashtag_rows = await list_hashtags(session)
        hashtag_ids_by_tag = {row.tag.lower(): row.id for row in hashtag_rows}
        seen_ids: set[int] = set()
        for tag in matched_tags:
            hashtag_id = hashtag_ids_by_tag.get(tag.lower())
            if hashtag_id is not None and hashtag_id not in seen_ids:
                seen_ids.add(hashtag_id)
                hashtag_ids.append(hashtag_id)
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
    logger.debug("[FIX] regenerate_announcement: raw_content_len=%d post_id=%d", len(raw), post_id)

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
        raw_matches = await match_hashtags(announcement, hashtag_rows)
        matched_tags = _sort_and_limit_hashtags(raw_matches, hashtag_rows)
        logger.info(
            "[FIX] regenerate_announcement: matched_tags=%s post_id=%d", matched_tags, post_id
        )
        matched_tags = await _fill_with_generated_hashtags(
            announcement, matched_tags, session=session, created_by=post.created_by
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


def _sort_and_limit_hashtags(
    matched_tags: list[str],
    hashtag_rows: list,
) -> list[str]:
    """
    Sort matched hashtags so required-category tags come first.
    Cap at 5; return empty list only when there are 0 matches.
    """
    if not matched_tags:
        logger.debug("[pipeline] _sort_and_limit_hashtags: no matched tags, returning empty list")
        return []
    required_set = {
        row.tag.lower()
        for row in hashtag_rows
        if row.category is not None and row.category.is_required
    }
    sorted_tags = sorted(matched_tags, key=lambda t: t.lower() not in required_set)
    final = sorted_tags[:5]
    logger.debug("[FIX] [pipeline] _sort_and_limit_hashtags: final=%d tags=%s", len(final), final)
    return final


async def _fill_with_generated_hashtags(
    announcement: str,
    matched_tags: list[str],
    session: AsyncSession,
    created_by: int,
    max_total: int = 5,
    max_generated: int = 2,
) -> list[str]:
    """
    If matched_tags has room (< max_total), ask AI to generate up to *max_generated*
    additional topical hashtags and save them to the DB in the "Свободная" category.
    """
    slots = max_total - len(matched_tags)
    if slots <= 0:
        return matched_tags
    to_generate = min(slots, max_generated)
    logger.debug(
        "[pipeline] _fill_with_generated_hashtags: db_tags=%d slots=%d to_generate=%d",
        len(matched_tags),
        slots,
        to_generate,
    )
    extra = await generate_extra_hashtags(announcement, to_generate)
    # Avoid duplicates with already-matched tags
    existing = {t.lower() for t in matched_tags}
    deduped = [t for t in extra if t.lower() not in existing]
    new_tags = deduped[:to_generate]

    # Save generated hashtags to DB in "Свободная" category
    if new_tags:
        try:
            category = await get_category_by_name(session, "Свободная")
            category_id = category.id if category else None
            for tag in new_tags:
                existing_row = await get_hashtag_by_tag(session, tag)
                if existing_row is None:
                    await create_hashtag(
                        session,
                        tag=tag,
                        created_by=created_by,
                        category_id=category_id,
                    )
                    logger.info(
                        "[pipeline] _fill_with_generated_hashtags: saved tag=%r to Свободная",
                        tag,
                    )
                else:
                    logger.debug(
                        "[pipeline] _fill_with_generated_hashtags: tag=%r already in DB, "
                        "skipping save",
                        tag,
                    )
        except Exception as exc:
            logger.error(
                "[pipeline] _fill_with_generated_hashtags: failed to save tags to DB error=%s",
                exc,
            )

    result = matched_tags + new_tags
    logger.info(
        "[pipeline] _fill_with_generated_hashtags: added %d generated tags=%s total=%d",
        len(new_tags),
        new_tags,
        len(result),
    )
    return result


async def _get_existing_post(session: AsyncSession, url: str) -> Post:
    """Helper: fetch an existing post by URL (guaranteed to exist after dedup check)."""
    from src.db.repository import get_post_by_url

    post = await get_post_by_url(session, url)
    assert post is not None, f"Expected post to exist for url={url!r}"
    return post
