import logging

import httpx
from bs4 import BeautifulSoup

from src.extractors.base import BaseExtractor, ExtractedContent, register_extractor
from src.extractors.detector import ContentType

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (compatible; TGPublisherBot/1.0; +https://github.com)"),
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
}
_REQUEST_TIMEOUT = 30.0
_MAX_TEXT_CHARS = 8000


@register_extractor(ContentType.article)
class ArticleExtractor(BaseExtractor):
    """Extract text, title, and author from a generic web article."""

    async def extract(self, url: str) -> ExtractedContent:
        logger.info("ArticleExtractor.extract: url=%r", url)

        async with httpx.AsyncClient(
            follow_redirects=True, timeout=_REQUEST_TIMEOUT, headers=_HEADERS
        ) as client:
            logger.debug("ArticleExtractor: fetching url=%r", url)
            response = await client.get(url)
            response.raise_for_status()
            logger.debug(
                "ArticleExtractor: got response status=%d content_type=%r",
                response.status_code,
                response.headers.get("content-type"),
            )

        soup = BeautifulSoup(response.text, "html.parser")

        title = _extract_title(soup)
        author = _extract_author(soup)
        text = _extract_text(soup)

        logger.info(
            "ArticleExtractor.extract: done url=%r title=%r author=%r text_len=%d",
            url,
            title,
            author,
            len(text),
        )
        return ExtractedContent(
            text=text,
            title=title,
            author=author,
            source_url=url,
            content_type=ContentType.article,
        )


def _extract_title(soup: BeautifulSoup) -> str | None:
    # Prefer og:title, then <title>
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):  # type: ignore[attr-defined]
        return og["content"].strip()  # type: ignore[index]
    tag = soup.find("title")
    if tag:
        return tag.get_text(strip=True)
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return None


def _extract_author(soup: BeautifulSoup) -> str | None:
    # Try common meta tags
    for attr, value in [
        ("name", "author"),
        ("property", "article:author"),
        ("name", "dc.creator"),
    ]:
        tag = soup.find("meta", {attr: value})
        if tag and tag.get("content"):  # type: ignore[attr-defined]
            return tag["content"].strip()  # type: ignore[index]

    # Try schema.org markup
    for sel in ["[itemprop='author']", ".author", ".byline"]:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            if text:
                return text

    return None


def _extract_text(soup: BeautifulSoup) -> str:
    # Remove script/style noise
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    # Prefer <article> or main content containers
    article = soup.find("article") or soup.find("main") or soup.body
    if article is None:
        return ""

    text = article.get_text(separator="\n", strip=True)
    # Collapse multiple blank lines
    lines = [line for line in text.splitlines() if line.strip()]
    cleaned = "\n".join(lines)
    return cleaned[:_MAX_TEXT_CHARS]
