import logging
from typing import TYPE_CHECKING

from src.ai.factory import get_ai_provider

if TYPE_CHECKING:
    from src.db.models import Hashtag

logger = logging.getLogger(__name__)


async def match_hashtags(post_text: str, hashtags: list["Hashtag"]) -> list[str]:
    """
    Ask the configured AI provider to pick 2-5 relevant hashtags from *hashtags*.
    Sends (tag, description) pairs so the AI can use descriptions to guide selection.
    Returns a list of hashtag strings (e.g. ["#tools", "#ai"]).
    Returns an empty list if no AI provider is configured, no hashtags are available,
    or if the provider call fails.
    """
    provider = get_ai_provider()
    if provider is None:
        logger.info("[FIX] match_hashtags: no AI provider configured, returning empty list")
        return []

    if not hashtags:
        logger.debug("match_hashtags: no available hashtags, returning empty list")
        return []

    logger.debug(
        "[hashtag_match] match_hashtags: provider=%s post_text_len=%d input_tags=%d",
        type(provider).__name__,
        len(post_text),
        len(hashtags),
    )

    try:
        result = await provider.match_hashtags(post_text, hashtags)
        logger.info("match_hashtags: matched=%s", result)
        return result
    except Exception as exc:
        logger.error("[FIX] match_hashtags: provider error=%s — returning empty list", exc)
        return []
