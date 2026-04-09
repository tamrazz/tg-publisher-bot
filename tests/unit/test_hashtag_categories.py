"""
Tests for hashtag category logic:
- required-category hashtags sorted first
- 2-5 hashtag limit enforcement
- category is_required determined by '!' prefix
- _fill_with_generated_hashtags fills remaining slots with AI tags (max 2)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.pipeline import _fill_with_generated_hashtags, _sort_and_limit_hashtags


def _make_hashtag(tag: str, is_required: bool = False) -> MagicMock:
    """Create a mock Hashtag row with a category."""
    cat = MagicMock()
    cat.is_required = is_required

    h = MagicMock()
    h.tag = tag
    h.category = cat
    return h


def _make_hashtag_no_cat(tag: str) -> MagicMock:
    """Create a mock Hashtag row without a category."""
    h = MagicMock()
    h.tag = tag
    h.category = None
    return h


def test_required_category_sorted_first() -> None:
    rows = [
        _make_hashtag("free1", is_required=False),
        _make_hashtag("req1", is_required=True),
        _make_hashtag("free2", is_required=False),
        _make_hashtag("req2", is_required=True),
    ]
    matched = ["free1", "req1", "free2", "req2"]

    result = _sort_and_limit_hashtags(matched, rows)

    assert result[0] in ("req1", "req2")
    assert result[1] in ("req1", "req2")
    assert result[2] in ("free1", "free2")
    assert result[3] in ("free1", "free2")


def test_single_hashtag_is_kept() -> None:
    # Previously a single match was dropped by a min-2 rule; now it's kept.
    rows = [_make_hashtag("only")]
    matched = ["only"]

    result = _sort_and_limit_hashtags(matched, rows)

    assert result == ["only"]


def test_min_2_hashtags_zero_enforced() -> None:
    result = _sort_and_limit_hashtags([], [])
    assert result == []


def test_exactly_2_hashtags_allowed() -> None:
    rows = [_make_hashtag("a"), _make_hashtag("b")]
    matched = ["a", "b"]

    result = _sort_and_limit_hashtags(matched, rows)

    assert len(result) == 2


def test_max_5_hashtags_enforced() -> None:
    rows = [_make_hashtag(f"t{i}") for i in range(8)]
    matched = [f"t{i}" for i in range(8)]

    result = _sort_and_limit_hashtags(matched, rows)

    assert len(result) == 5


def test_category_is_required_from_exclamation_prefix() -> None:
    """'!' prefix → is_required=True; no prefix → is_required=False."""
    raw_with_bang = "!Тематика"
    is_required = raw_with_bang.startswith("!")
    name = raw_with_bang.lstrip("!").strip()

    assert is_required is True
    assert name == "Тематика"


def test_category_is_not_required_without_prefix() -> None:
    raw = "Технологии"
    is_required = raw.startswith("!")
    name = raw.lstrip("!").strip()

    assert is_required is False
    assert name == "Технологии"


def test_no_category_hashtags_not_treated_as_required() -> None:
    rows = [
        _make_hashtag_no_cat("nocategory"),
        _make_hashtag("free", is_required=False),
        _make_hashtag("req", is_required=True),
    ]
    matched = ["nocategory", "free", "req"]

    result = _sort_and_limit_hashtags(matched, rows)

    assert result[0] == "req"
    assert len(result) == 3


# ---------------------------------------------------------------------------
# _fill_with_generated_hashtags tests
# ---------------------------------------------------------------------------


def _mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.mark.asyncio
async def test_fill_adds_generated_when_slots_remain() -> None:
    with (
        patch(
            "src.services.pipeline.generate_extra_hashtags",
            new=AsyncMock(return_value=["aiml", "opensource"]),
        ),
        patch("src.services.pipeline.get_category_by_name", new=AsyncMock(return_value=None)),
        patch("src.services.pipeline.get_hashtag_by_tag", new=AsyncMock(return_value=None)),
        patch("src.services.pipeline.create_hashtag", new=AsyncMock()),
    ):
        result = await _fill_with_generated_hashtags(
            "some post text", ["python", "tools"], session=_mock_session(), created_by=1
        )

    assert "python" in result
    assert "tools" in result
    assert "aiml" in result or "opensource" in result
    assert len(result) <= 5


@pytest.mark.asyncio
async def test_fill_no_extra_when_already_5() -> None:
    tags = ["a", "b", "c", "d", "e"]
    with patch(
        "src.services.pipeline.generate_extra_hashtags",
        new=AsyncMock(return_value=["extra"]),
    ) as mock_gen:
        result = await _fill_with_generated_hashtags(
            "text", tags, session=_mock_session(), created_by=1
        )

    mock_gen.assert_not_called()
    assert result == tags


@pytest.mark.asyncio
async def test_fill_deduplicates_generated_tags() -> None:
    with (
        patch(
            "src.services.pipeline.generate_extra_hashtags",
            new=AsyncMock(return_value=["python", "newone"]),  # "python" already matched
        ),
        patch("src.services.pipeline.get_category_by_name", new=AsyncMock(return_value=None)),
        patch("src.services.pipeline.get_hashtag_by_tag", new=AsyncMock(return_value=None)),
        patch("src.services.pipeline.create_hashtag", new=AsyncMock()),
    ):
        result = await _fill_with_generated_hashtags(
            "text", ["python"], session=_mock_session(), created_by=1
        )

    assert result.count("python") == 1
    assert "newone" in result


@pytest.mark.asyncio
async def test_fill_generates_at_most_2_extra() -> None:
    with (
        patch(
            "src.services.pipeline.generate_extra_hashtags",
            new=AsyncMock(return_value=["x", "y"]),
        ) as mock_gen,
        patch("src.services.pipeline.get_category_by_name", new=AsyncMock(return_value=None)),
        patch("src.services.pipeline.get_hashtag_by_tag", new=AsyncMock(return_value=None)),
        patch("src.services.pipeline.create_hashtag", new=AsyncMock()),
    ):
        await _fill_with_generated_hashtags("text", [], session=_mock_session(), created_by=1)

    # count passed to generate_extra_hashtags should be <= 2
    call_count_arg = mock_gen.call_args[0][1]
    assert call_count_arg <= 2
