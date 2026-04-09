import logging

from src.ai.factory import get_ai_provider

logger = logging.getLogger(__name__)


async def generate_extra_hashtags(post_text: str, count: int) -> list[str]:
    """
    Ask the AI to generate *count* topical hashtags for *post_text*.
    Tags are not taken from the DB. Saving to DB is the caller's responsibility.
    Returns a list of tag strings without '#' (same format as DB tags).
    Returns [] if count <= 0, no AI provider, or on provider error.
    """
    if count <= 0:
        return []

    provider = get_ai_provider()
    if provider is None:
        logger.info(
            "[FIX] generate_extra_hashtags: no AI provider configured, skipping"
        )
        return []

    logger.debug(
        "[FIX] generate_extra_hashtags: provider=%s post_text_len=%d count=%d",
        type(provider).__name__,
        len(post_text),
        count,
    )
    try:
        result = await provider.generate_hashtags(post_text, count)
        logger.info("[FIX] generate_extra_hashtags: generated=%s", result)
        return result
    except Exception as exc:
        logger.error(
            "[FIX] generate_extra_hashtags: provider error=%s — returning empty list", exc
        )
        return []
