import logging

from src.ai.factory import get_ai_provider
from src.extractors.base import ExtractedContent

logger = logging.getLogger(__name__)


async def summarize(content: ExtractedContent) -> str | None:
    """
    Generate a 2-3 sentence Russian-language announcement for *content*.

    Returns the announcement text, or None if no AI provider is configured or
    if the provider call fails (pipeline will publish the URL without an announcement).
    """
    provider = get_ai_provider()
    if provider is None:
        logger.info("[FIX] summarize: no AI provider configured, skipping summarization")
        return None

    logger.info(
        "summarize: provider=%s content_type=%s title=%r text_len=%d",
        type(provider).__name__,
        content.content_type,
        content.title,
        len(content.text),
    )

    try:
        result = await provider.summarize(content)
        logger.info("summarize: done result_len=%d", len(result))
        logger.debug("summarize: result=%r", result)
        return result
    except Exception as exc:
        logger.error("[FIX] summarize: provider error=%s — falling back to URL-only post", exc)
        return None
