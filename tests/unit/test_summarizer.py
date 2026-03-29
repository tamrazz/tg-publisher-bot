from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai.base import BaseAIProvider
from src.ai.hashtag_matcher import match_hashtags
from src.ai.summarizer import summarize
from src.extractors.base import ExtractedContent
from src.extractors.detector import ContentType


def make_content(
    text: str = "Some article text.",
    title: str | None = "Article Title",
    author: str | None = "John Doe",
    url: str = "https://example.com/article",
    content_type: ContentType = ContentType.article,
) -> ExtractedContent:
    return ExtractedContent(
        text=text,
        title=title,
        author=author,
        source_url=url,
        content_type=content_type,
    )


def make_mock_provider(summarize_result: str = "Краткое описание. © Author") -> MagicMock:
    """Return a mock BaseAIProvider with pre-configured return values."""
    provider = MagicMock(spec=BaseAIProvider)
    provider.summarize = AsyncMock(return_value=summarize_result)
    provider.match_hashtags = AsyncMock(return_value=[])
    return provider


# ---------------------------------------------------------------------------
# Summarizer tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_returns_string() -> None:
    mock_provider = make_mock_provider("Краткое описание статьи. © John Doe")
    with patch("src.ai.summarizer.get_ai_provider", return_value=mock_provider):
        result = await summarize(make_content())

    assert isinstance(result, str)
    assert "Краткое описание" in result
    mock_provider.summarize.assert_called_once()


@pytest.mark.asyncio
async def test_summarize_passes_content_to_provider() -> None:
    mock_provider = make_mock_provider("Summary text.")
    with patch("src.ai.summarizer.get_ai_provider", return_value=mock_provider):
        content = make_content(title="My Title", author="My Author")
        await summarize(content)

    mock_provider.summarize.assert_called_once_with(content)


@pytest.mark.asyncio
async def test_summarize_returns_none_when_no_provider() -> None:
    """summarize() returns None when AI_PROVIDER is not configured."""
    with patch("src.ai.summarizer.get_ai_provider", return_value=None):
        result = await summarize(make_content())

    assert result is None


@pytest.mark.asyncio
async def test_summarize_returns_none_on_provider_error() -> None:
    """summarize() returns None (instead of raising) when the provider call fails."""
    mock_provider = MagicMock(spec=BaseAIProvider)
    mock_provider.summarize = AsyncMock(side_effect=Exception("API error"))
    with patch("src.ai.summarizer.get_ai_provider", return_value=mock_provider):
        result = await summarize(make_content())

    assert result is None


# ---------------------------------------------------------------------------
# Hashtag matcher tests
# ---------------------------------------------------------------------------


def test_parse_hashtags_basic() -> None:
    # _parse_hashtags is now a method on BaseAIProvider — test via a concrete provider
    from src.ai.providers.claude import ClaudeProvider

    provider = ClaudeProvider.__new__(ClaudeProvider)
    available = ["#tools", "#ai", "#python", "#web"]
    result = provider._parse_hashtags("#tools #ai", available)
    assert result == ["#tools", "#ai"]


def test_parse_hashtags_filters_unavailable() -> None:
    from src.ai.providers.claude import ClaudeProvider

    provider = ClaudeProvider.__new__(ClaudeProvider)
    result = provider._parse_hashtags("#tools #nonexistent #python", ["#tools", "#ai"])
    assert result == ["#tools"]


def test_parse_hashtags_max_three() -> None:
    from src.ai.providers.claude import ClaudeProvider

    provider = ClaudeProvider.__new__(ClaudeProvider)
    result = provider._parse_hashtags("#a #b #c #d", ["#a", "#b", "#c", "#d"])
    assert len(result) <= 3


def test_parse_hashtags_empty_response() -> None:
    from src.ai.providers.claude import ClaudeProvider

    provider = ClaudeProvider.__new__(ClaudeProvider)
    assert provider._parse_hashtags("", ["#tools"]) == []


def test_parse_hashtags_case_insensitive() -> None:
    from src.ai.providers.claude import ClaudeProvider

    provider = ClaudeProvider.__new__(ClaudeProvider)
    available = ["#Tools", "#AI"]
    result = provider._parse_hashtags("#tools #ai", available)
    assert len(result) >= 1


@pytest.mark.asyncio
async def test_match_hashtags_empty_available() -> None:
    result = await match_hashtags("some text", [])
    assert result == []


@pytest.mark.asyncio
async def test_match_hashtags_returns_empty_when_no_provider() -> None:
    """match_hashtags() returns [] when AI_PROVIDER is not configured."""
    with patch("src.ai.hashtag_matcher.get_ai_provider", return_value=None):
        result = await match_hashtags("Article about AI tools", ["#tools", "#ai"])

    assert result == []


@pytest.mark.asyncio
async def test_match_hashtags_calls_provider() -> None:
    mock_provider = make_mock_provider()
    mock_provider.match_hashtags = AsyncMock(return_value=["#tools", "#ai"])
    with patch("src.ai.hashtag_matcher.get_ai_provider", return_value=mock_provider):
        result = await match_hashtags("Article about AI tools", ["#tools", "#ai", "#news"])

    assert "#tools" in result
    assert "#ai" in result
    mock_provider.match_hashtags.assert_called_once()


@pytest.mark.asyncio
async def test_match_hashtags_returns_empty_on_provider_error() -> None:
    mock_provider = MagicMock(spec=BaseAIProvider)
    mock_provider.match_hashtags = AsyncMock(side_effect=Exception("API error"))
    with patch("src.ai.hashtag_matcher.get_ai_provider", return_value=mock_provider):
        result = await match_hashtags("some text", ["#tools"])

    assert result == []
