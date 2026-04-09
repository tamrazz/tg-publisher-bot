import logging
import re
from enum import StrEnum

logger = logging.getLogger(__name__)

# Patterns for URL type detection
_YOUTUBE_PATTERN = re.compile(
    r"(https?://)?(www\.)?(youtube\.com/(watch|shorts|embed|live)|youtu\.be/)",
    re.IGNORECASE,
)
_GITHUB_PATTERN = re.compile(
    r"(https?://)?(www\.)?github\.com/[^/]+/[^/]+",
    re.IGNORECASE,
)
_AUDIO_PATTERN = re.compile(
    r"\.(mp3|wav|ogg|flac|aac|m4a|opus)(\?.*)?$",
    re.IGNORECASE,
)


class ContentType(StrEnum):
    article = "article"
    youtube = "youtube"
    github = "github"
    audio = "audio"


def detect_content_type(url: str) -> ContentType:
    """
    Detect the content type of *url* by pattern matching.

    Order of precedence:
    1. YouTube
    2. GitHub
    3. Direct audio file
    4. Generic article (fallback)
    """
    logger.debug("detect_content_type: url=%r", url)

    if _YOUTUBE_PATTERN.search(url):
        logger.debug("detect_content_type: detected YOUTUBE for url=%r", url)
        return ContentType.youtube

    if _GITHUB_PATTERN.search(url):
        logger.debug("detect_content_type: detected GITHUB for url=%r", url)
        return ContentType.github

    if _AUDIO_PATTERN.search(url):
        logger.debug("detect_content_type: detected AUDIO for url=%r", url)
        return ContentType.audio

    logger.debug("detect_content_type: detected ARTICLE (fallback) for url=%r", url)
    return ContentType.article
