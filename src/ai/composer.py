import logging

logger = logging.getLogger(__name__)


def compose_post(
    announcement: str | None,
    source_url: str,
    hashtags: list[str],
) -> str:
    """
    Assemble the final Telegram post HTML string.

    If *announcement* is provided:
        <announcement text (includes © copyright line if present)>

        <source_url>

        <hashtags>

    If *announcement* is None (no AI provider or error):
        <source_url>
    """
    logger.debug(
        "compose_post: has_announcement=%s source_url=%r hashtags=%s",
        announcement is not None,
        source_url,
        hashtags,
    )

    parts = []
    if announcement:
        parts.append(announcement.strip())
        parts.append("")  # blank line before URL
    parts.append(source_url)

    if hashtags:
        parts.append("")  # blank line before hashtags
        parts.append(" ".join(hashtags))

    result = "\n".join(parts)
    logger.debug("compose_post: result_len=%d", len(result))
    return result
