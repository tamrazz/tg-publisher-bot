from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai.composer import compose_post
from src.extractors.base import ExtractedContent
from src.extractors.detector import ContentType

# ---------------------------------------------------------------------------
# Composer tests (pure function, no mocking needed)
# ---------------------------------------------------------------------------


def test_compose_post_no_announcement() -> None:
    """When announcement is None, post contains only the URL."""
    result = compose_post(announcement=None, source_url="https://example.com", hashtags=[])
    assert result == "https://example.com"
    assert "None" not in result


def test_compose_post_no_announcement_no_hashtags() -> None:
    """Hashtags are omitted when announcement is None (URL-only fallback)."""
    result = compose_post(
        announcement=None,
        source_url="https://example.com",
        hashtags=["#ai"],
    )
    # hashtags should still appear even without announcement
    assert "https://example.com" in result


def test_compose_post_basic() -> None:
    result = compose_post(
        announcement="Краткое описание. © Автор",
        source_url="https://example.com/article",
        hashtags=["#tools", "#ai"],
    )
    assert "Краткое описание" in result
    assert "https://example.com/article" in result
    assert "#tools #ai" in result


def test_compose_post_no_hashtags() -> None:
    result = compose_post(
        announcement="Some text.",
        source_url="https://example.com",
        hashtags=[],
    )
    assert "Some text." in result
    assert "https://example.com" in result
    assert "#" not in result


def test_compose_post_announcement_first() -> None:
    result = compose_post(
        announcement="First line.",
        source_url="https://example.com",
        hashtags=[],
    )
    lines = result.strip().splitlines()
    assert lines[0] == "First line."


def test_compose_post_url_before_hashtags() -> None:
    result = compose_post(
        announcement="Text.",
        source_url="https://example.com",
        hashtags=["#tag"],
    )
    url_pos = result.index("https://example.com")
    tag_pos = result.index("#tag")
    assert url_pos < tag_pos


# ---------------------------------------------------------------------------
# Pipeline integration (mocked)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_deduplication(monkeypatch) -> None:
    """Pipeline should return already_exists=True if URL was processed before."""
    from src.services import pipeline

    mock_session = MagicMock()
    mock_bot = MagicMock()

    # Mock is_url_processed to return True
    with patch("src.services.pipeline.is_url_processed", AsyncMock(return_value=True)):
        with patch(
            "src.services.pipeline._get_existing_post",
            AsyncMock(
                return_value=MagicMock(
                    id=1,
                    post_text="Existing post text",
                    status="published",
                )
            ),
        ):
            result = await pipeline.process_url(
                url="https://example.com/already-done",
                created_by=123,
                session=mock_session,
                bot=mock_bot,
                moderate=True,
            )

    assert result.already_exists is True


@pytest.mark.asyncio
async def test_pipeline_runs_full_flow(monkeypatch) -> None:
    """Pipeline should call extract → summarize → match_hashtags → compose → create_post."""
    from src.services import pipeline

    mock_session = MagicMock()
    mock_bot = MagicMock()

    fake_content = ExtractedContent(
        text="Article text",
        title="Title",
        author="Author",
        source_url="https://example.com/new",
        content_type=ContentType.article,
    )
    fake_post = MagicMock(id=42, post_text="Composed post.", status="pending")

    with (
        patch("src.services.pipeline.is_url_processed", AsyncMock(return_value=False)),
        patch(
            "src.services.pipeline.detect_content_type",
            return_value=ContentType.article,
        ),
        patch(
            "src.services.pipeline.get_extractor",
            return_value=MagicMock(extract=AsyncMock(return_value=fake_content)),
        ),
        patch(
            "src.services.pipeline.summarize",
            AsyncMock(return_value="Краткое описание. © Author"),
        ),
        patch("src.services.pipeline.list_hashtags", AsyncMock(return_value=[])),
        patch("src.services.pipeline.match_hashtags", AsyncMock(return_value=[])),
        patch("src.services.pipeline.create_post", AsyncMock(return_value=fake_post)),
        patch("src.services.pipeline.attach_hashtags_to_post", AsyncMock()),
    ):
        result = await pipeline.process_url(
            url="https://example.com/new",
            created_by=123,
            session=mock_session,
            bot=mock_bot,
            moderate=True,
        )

    assert result.already_exists is False
    assert result.post.id == 42
    assert result.published is False  # moderate=True means not yet published


@pytest.mark.asyncio
async def test_pipeline_url_only_when_no_ai(monkeypatch) -> None:
    """When summarize() returns None (no AI provider), post_text contains only the URL."""
    from src.services import pipeline

    mock_session = MagicMock()
    mock_bot = MagicMock()
    url = "https://example.com/no-ai"

    fake_content = ExtractedContent(
        text="Article text",
        title="Title",
        author="Author",
        source_url=url,
        content_type=ContentType.article,
    )
    fake_post = MagicMock(id=99, post_text=url, status="pending")

    with (
        patch("src.services.pipeline.is_url_processed", AsyncMock(return_value=False)),
        patch("src.services.pipeline.detect_content_type", return_value=ContentType.article),
        patch(
            "src.services.pipeline.get_extractor",
            return_value=MagicMock(extract=AsyncMock(return_value=fake_content)),
        ),
        patch("src.services.pipeline.summarize", AsyncMock(return_value=None)),
        patch("src.services.pipeline.create_post", AsyncMock(return_value=fake_post)),
        patch("src.services.pipeline.attach_hashtags_to_post", AsyncMock()),
    ):
        result = await pipeline.process_url(
            url=url,
            created_by=123,
            session=mock_session,
            bot=mock_bot,
            moderate=True,
        )

    # post_text should be just the URL — no announcement, no hashtags
    assert result.post_text == url
