import pytest

from src.extractors.detector import ContentType, detect_content_type


@pytest.mark.parametrize(
    "url, expected",
    [
        # YouTube variants
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", ContentType.youtube),
        ("https://youtu.be/dQw4w9WgXcQ", ContentType.youtube),
        ("https://youtube.com/shorts/abc123defgh", ContentType.youtube),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", ContentType.youtube),
        ("https://www.youtube.com/live/abc1234abcd", ContentType.youtube),
        # GitHub variants
        ("https://github.com/python/cpython", ContentType.github),
        ("https://github.com/torvalds/linux", ContentType.github),
        ("https://www.github.com/openai/openai-python", ContentType.github),
        # Audio variants
        ("https://example.com/podcast.mp3", ContentType.audio),
        ("https://cdn.example.com/audio.wav", ContentType.audio),
        ("https://files.example.com/track.flac", ContentType.audio),
        ("https://storage.example.com/ep01.ogg", ContentType.audio),
        ("https://media.example.com/clip.m4a?token=abc", ContentType.audio),
        # Article fallback
        ("https://example.com/blog/post-title", ContentType.article),
        ("https://medium.com/@author/some-article", ContentType.article),
        ("http://habr.com/ru/articles/12345/", ContentType.article),
        ("https://news.ycombinator.com/item?id=12345", ContentType.article),
    ],
)
def test_detect_content_type(url: str, expected: ContentType) -> None:
    result = detect_content_type(url)
    assert result == expected, f"Expected {expected} for URL {url!r}, got {result}"


def test_detect_content_type_returns_content_type_enum() -> None:
    result = detect_content_type("https://example.com")
    assert isinstance(result, ContentType)


def test_youtube_takes_priority_over_article() -> None:
    # YouTube URL should never be detected as article
    url = "https://www.youtube.com/watch?v=test123test"
    assert detect_content_type(url) == ContentType.youtube


def test_github_takes_priority_over_article() -> None:
    url = "https://github.com/user/repo"
    assert detect_content_type(url) == ContentType.github
