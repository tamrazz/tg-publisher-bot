import logging

from src.ai.factory import get_ai_provider

logger = logging.getLogger(__name__)


async def match_hashtags(post_text: str, available_hashtags: list[str]) -> list[str]:
    """
    Ask the configured AI provider to pick 1-3 relevant hashtags from *available_hashtags*.
    Returns a list of hashtag strings (e.g. ["#tools", "#ai"]).
    Returns an empty list if no AI provider is configured, no hashtags are available,
    or if the provider call fails.
    """
    provider = get_ai_provider()
    if provider is None:
        logger.info("[FIX] match_hashtags: no AI provider configured, returning empty list")
        return []

    if not available_hashtags:
        logger.debug("match_hashtags: no available hashtags, returning empty list")
        return []

    logger.info(
        "match_hashtags: provider=%s post_text_len=%d available_count=%d",
        type(provider).__name__,
        len(post_text),
        len(available_hashtags),
    )

    try:
        result = await provider.match_hashtags(post_text, available_hashtags)
        logger.info("match_hashtags: matched=%s", result)
        return result
    except Exception as exc:
        logger.error("[FIX] match_hashtags: provider error=%s — returning empty list", exc)
        return []
