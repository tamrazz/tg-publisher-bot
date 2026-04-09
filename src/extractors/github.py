import logging
import re

import httpx

from src.config import settings
from src.extractors.base import BaseExtractor, ExtractedContent, register_extractor
from src.extractors.detector import ContentType

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_MAX_README_CHARS = 8000
_REQUEST_TIMEOUT = 20.0


def _parse_repo(url: str) -> tuple[str, str] | None:
    """Return (owner, repo) from a GitHub URL, or None."""
    match = re.search(r"github\.com/([^/]+)/([^/?#]+)", url, re.IGNORECASE)
    if match:
        return match.group(1), match.group(2).removesuffix(".git")
    return None


@register_extractor(ContentType.github)
class GitHubExtractor(BaseExtractor):
    """Fetch repository metadata + README from GitHub REST API."""

    async def extract(self, url: str) -> ExtractedContent:
        logger.info("GitHubExtractor.extract: url=%r", url)

        parsed = _parse_repo(url)
        if parsed is None:
            raise ValueError(f"Cannot parse owner/repo from GitHub URL: {url!r}")

        owner, repo = parsed
        logger.debug("GitHubExtractor.extract: owner=%r repo=%r", owner, repo)

        headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"
            logger.debug("GitHubExtractor: using GitHub token")

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT, headers=headers) as client:
            # Fetch repo metadata
            logger.debug("GitHubExtractor: fetching repo metadata owner=%r repo=%r", owner, repo)
            repo_resp = await client.get(f"{_GITHUB_API}/repos/{owner}/{repo}")
            repo_resp.raise_for_status()
            repo_data = repo_resp.json()

            # Fetch README
            logger.debug("GitHubExtractor: fetching README owner=%r repo=%r", owner, repo)
            readme_resp = await client.get(
                f"{_GITHUB_API}/repos/{owner}/{repo}/readme",
                headers={**headers, "Accept": "application/vnd.github.raw+json"},
            )

        title = repo_data.get("full_name")
        description = repo_data.get("description") or ""
        stars = repo_data.get("stargazers_count", 0)
        language = repo_data.get("language") or ""

        readme_text = ""
        if readme_resp.status_code == 200:
            readme_text = readme_resp.text[:_MAX_README_CHARS]
            logger.debug("GitHubExtractor: got README len=%d", len(readme_text))
        else:
            logger.warning(
                "GitHubExtractor: README not found owner=%r repo=%r status=%d",
                owner,
                repo,
                readme_resp.status_code,
            )

        text = (
            f"Repository: {title}\n"
            f"Description: {description}\n"
            f"Language: {language}\n"
            f"Stars: {stars}\n\n"
            f"README:\n{readme_text}"
        )

        logger.info(
            "GitHubExtractor.extract: done url=%r title=%r text_len=%d",
            url,
            title,
            len(text),
        )
        return ExtractedContent(
            text=text,
            title=title,
            author=owner,
            source_url=url,
            content_type=ContentType.github,
        )
