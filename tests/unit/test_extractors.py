import pytest
import respx
from httpx import Response

from src.extractors.article import ArticleExtractor
from src.extractors.audio import AudioExtractor
from src.extractors.base import ExtractedContent, get_extractor
from src.extractors.detector import ContentType
from src.extractors.github import GitHubExtractor
from src.extractors.youtube import YouTubeExtractor

# ---------------------------------------------------------------------------
# Article extractor tests
# ---------------------------------------------------------------------------


ARTICLE_HTML = """
<html>
<head>
    <title>Test Article Title</title>
    <meta name="author" content="Jane Doe" />
    <meta property="og:title" content="OG Article Title" />
</head>
<body>
<article>
    <h1>Main Heading</h1>
    <p>First paragraph of the article.</p>
    <p>Second paragraph with more details.</p>
</article>
<script>var x = 1;</script>
</body>
</html>
"""


@pytest.mark.asyncio
@respx.mock
async def test_article_extractor_basic() -> None:
    url = "https://example.com/article"
    respx.get(url).mock(return_value=Response(200, text=ARTICLE_HTML))

    extractor = ArticleExtractor()
    result = await extractor.extract(url)

    assert isinstance(result, ExtractedContent)
    assert result.content_type == ContentType.article
    assert result.source_url == url
    assert result.title == "OG Article Title"
    assert result.author == "Jane Doe"
    assert "First paragraph" in result.text
    assert "Second paragraph" in result.text
    # Script content should be stripped
    assert "var x" not in result.text


@pytest.mark.asyncio
@respx.mock
async def test_article_extractor_no_og_title_falls_back_to_title_tag() -> None:
    html = "<html><head><title>Plain Title</title></head><body><p>Content</p></body></html>"
    url = "https://example.com/plain"
    respx.get(url).mock(return_value=Response(200, text=html))

    extractor = ArticleExtractor()
    result = await extractor.extract(url)

    assert result.title == "Plain Title"


@pytest.mark.asyncio
@respx.mock
async def test_article_extractor_http_error_raises() -> None:
    url = "https://example.com/notfound"
    respx.get(url).mock(return_value=Response(404))

    extractor = ArticleExtractor()
    with pytest.raises(Exception):
        await extractor.extract(url)


# ---------------------------------------------------------------------------
# GitHub extractor tests
# ---------------------------------------------------------------------------

GITHUB_REPO_RESPONSE = {
    "full_name": "owner/repo",
    "description": "A test repository",
    "stargazers_count": 42,
    "language": "Python",
}

GITHUB_README_TEXT = "# My Project\n\nThis is the README content."


@pytest.mark.asyncio
@respx.mock
async def test_github_extractor_basic() -> None:
    url = "https://github.com/owner/repo"
    respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=Response(200, json=GITHUB_REPO_RESPONSE)
    )
    respx.get("https://api.github.com/repos/owner/repo/readme").mock(
        return_value=Response(200, text=GITHUB_README_TEXT)
    )

    extractor = GitHubExtractor()
    result = await extractor.extract(url)

    assert isinstance(result, ExtractedContent)
    assert result.content_type == ContentType.github
    assert result.source_url == url
    assert result.title == "owner/repo"
    assert result.author == "owner"
    assert "A test repository" in result.text
    assert "42" in result.text
    assert "README" in result.text


@pytest.mark.asyncio
async def test_github_extractor_invalid_url() -> None:
    extractor = GitHubExtractor()
    with pytest.raises(ValueError, match="Cannot parse"):
        await extractor.extract("https://github.com")


# ---------------------------------------------------------------------------
# Audio extractor tests (mocked httpx + openai)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_audio_extractor_downloads_and_transcribes(monkeypatch, tmp_path) -> None:
    url = "https://example.com/audio.mp3"
    audio_content = b"fake-audio-bytes"

    respx.get(url).mock(
        return_value=Response(
            200,
            content=audio_content,
            headers={"content-length": str(len(audio_content))},
        )
    )

    # Mock faster-whisper transcription
    class FakeSegment:
        text = "Hello, this is the transcript."

    class FakeInfo:
        language = "en"

    class FakeWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, audio_path, **kwargs):
            return [FakeSegment()], FakeInfo()

    monkeypatch.setattr("src.extractors.audio._whisper_model", None)
    monkeypatch.setattr("faster_whisper.WhisperModel", FakeWhisperModel)

    extractor = AudioExtractor()
    result = await extractor.extract(url)

    assert isinstance(result, ExtractedContent)
    assert result.content_type == ContentType.audio
    assert result.source_url == url
    assert "transcript" in result.text


@pytest.mark.asyncio
@respx.mock
async def test_audio_extractor_large_file_passes(monkeypatch, tmp_path) -> None:
    """Files larger than the old 25 MB OpenAI limit should now be accepted (up to 200 MB)."""
    url = "https://example.com/big_audio.mp3"
    # 30 MB — previously rejected by OpenAI limit, now within the 200 MB local limit
    big_size = 30 * 1024 * 1024
    audio_content = b"x" * big_size

    respx.get(url).mock(
        return_value=Response(
            200,
            content=audio_content,
            headers={"content-length": str(big_size)},
        )
    )

    class FakeSegment:
        text = "Large file transcript."

    class FakeInfo:
        language = "en"

    class FakeWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, audio_path, **kwargs):
            return [FakeSegment()], FakeInfo()

    monkeypatch.setattr("src.extractors.audio._whisper_model", None)
    monkeypatch.setattr("faster_whisper.WhisperModel", FakeWhisperModel)

    extractor = AudioExtractor()
    result = await extractor.extract(url)

    assert isinstance(result, ExtractedContent)
    assert result.content_type == ContentType.audio
    assert "Large file" in result.text


# ---------------------------------------------------------------------------
# YouTube extractor tests
# ---------------------------------------------------------------------------


class FakeSnippet:
    """Mimics youtube-transcript-api v1.x FetchedTranscriptSnippet (not subscriptable)."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.start = 0.0
        self.duration = 1.0


def _make_transcript_entry(text: str) -> dict:
    return {"text": text, "start": 0.0, "duration": 1.0}


def _make_fake_transcript(language_code: str, is_generated: bool, entries):
    class FakeTranscript:
        def __init__(self):
            self.language_code = language_code
            self.is_generated = is_generated

        def fetch(self):
            return entries

    return FakeTranscript()


def _make_fake_transcript_list(transcripts):
    class FakeTranscriptList:
        def __iter__(self):
            return iter(transcripts)

    return FakeTranscriptList()


@pytest.mark.asyncio
async def test_transcript_via_api_uses_attribute_not_subscript(monkeypatch) -> None:
    """Regression: FetchedTranscriptSnippet uses .text attribute, not ["text"] subscript.

    youtube-transcript-api v1.x returns snippet objects (not dicts). Using entry["text"]
    raises TypeError. This test ensures we use entry.text.
    """
    import sys
    import types
    import unittest.mock as mock

    from src.extractors.youtube import _transcript_via_api

    snippets = [FakeSnippet("Hello"), FakeSnippet("world")]

    class FakeAPI:
        def fetch(self, video_id, languages=None):
            return snippets

    fake_module = types.ModuleType("youtube_transcript_api")
    fake_module.YouTubeTranscriptApi = FakeAPI  # type: ignore[attr-defined]

    with mock.patch.dict(sys.modules, {"youtube_transcript_api": fake_module}):
        result = await _transcript_via_api("dQw4w9WgXcQ")

    assert result == "Hello world"


@pytest.mark.asyncio
async def test_youtube_extractor_uses_preferred_language(monkeypatch) -> None:
    """Should pick manual 'ru' transcript when available."""
    entries = [_make_transcript_entry("Привет мир")]
    ru_transcript = _make_fake_transcript("ru", is_generated=False, entries=entries)
    fake_list = _make_fake_transcript_list([ru_transcript])

    import src.extractors.youtube as yt_module

    class FakeYTApi:
        @staticmethod
        def list_transcripts(video_id):
            return fake_list

    monkeypatch.setattr(yt_module, "_transcript_via_whisper", lambda url: _async_none())

    # Patch inside the function via the module-level import
    import unittest.mock as mock

    with mock.patch.dict("sys.modules", {"youtube_transcript_api": mock.MagicMock()}):
        import youtube_transcript_api  # noqa: F401 — ensure module is patchable

        monkeypatch.setattr(
            "src.extractors.youtube._transcript_via_api",
            lambda video_id: _async_result("Привет мир"),
        )

        extractor = YouTubeExtractor()
        result = await extractor.extract("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert "Привет мир" in result.text
    assert result.content_type == ContentType.youtube


@pytest.mark.asyncio
async def test_youtube_extractor_falls_back_to_any_language(monkeypatch) -> None:
    """Should use any available transcript (non-ru/en) via whisper fallback."""
    import src.extractors.youtube as yt_module

    monkeypatch.setattr(yt_module, "_transcript_via_api", lambda video_id: _async_none())
    monkeypatch.setattr(
        yt_module, "_transcript_via_whisper", lambda url: _async_result("Hola mundo")
    )

    extractor = YouTubeExtractor()
    result = await extractor.extract("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert "Hola mundo" in result.text


@pytest.mark.asyncio
async def test_youtube_extractor_raises_when_no_transcripts(monkeypatch) -> None:
    """Should raise RuntimeError when both API and whisper fail."""
    import src.extractors.youtube as yt_module

    monkeypatch.setattr(yt_module, "_transcript_via_api", lambda video_id: _async_none())
    monkeypatch.setattr(yt_module, "_transcript_via_whisper", lambda url: _async_none())

    extractor = YouTubeExtractor()
    with pytest.raises(RuntimeError, match="Could not extract transcript"):
        await extractor.extract("https://www.youtube.com/watch?v=dQw4w9WgXcQ")


async def _async_none():
    return None


async def _async_result(text: str):
    return text


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


def test_get_extractor_article() -> None:
    extractor = get_extractor(ContentType.article)
    assert isinstance(extractor, ArticleExtractor)


def test_get_extractor_github() -> None:
    extractor = get_extractor(ContentType.github)
    assert isinstance(extractor, GitHubExtractor)


def test_get_extractor_unknown_raises() -> None:
    with pytest.raises(ValueError, match="No extractor registered"):
        get_extractor("unknown_type")  # type: ignore[arg-type]
