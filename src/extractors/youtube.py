import asyncio
import logging
import os
import re
import tempfile

from src.extractors.base import BaseExtractor, ExtractedContent, register_extractor
from src.extractors.detector import ContentType

logger = logging.getLogger(__name__)

# Groq free tier hard limit: 12 000 TPM. Overhead (system prompt + URL) ≈ 1 400 tokens.
# At ~3.5 chars/token that leaves ~37 000 chars of safe content budget.
# We use 32 000 to keep a comfortable buffer.
_MAX_TRANSCRIPT_CHARS = 32_000


def _smart_truncate(text: str, max_chars: int) -> str:
    """
    Fit *text* into *max_chars* by sampling uniformly:
    40% from the beginning, 20% from the middle, 40% from the end.
    Short texts (≤ max_chars) are returned unchanged.
    """
    if len(text) <= max_chars:
        return text

    head = int(max_chars * 0.4)
    tail = int(max_chars * 0.4)
    mid_size = max_chars - head - tail
    mid_start = (len(text) - mid_size) // 2

    logger.debug(
        "[FIX] _smart_truncate: full_len=%d max=%d head=%d mid=%d tail=%d",
        len(text), max_chars, head, mid_size, tail,
    )
    return (
        text[:head]
        + "\n\n[...]\n\n"
        + text[mid_start : mid_start + mid_size]
        + "\n\n[...]\n\n"
        + text[-tail:]
    )


def _extract_video_id(url: str) -> str | None:
    patterns = [
        r"youtube\.com/watch\?v=([A-Za-z0-9_-]{11})",
        r"youtu\.be/([A-Za-z0-9_-]{11})",
        r"youtube\.com/shorts/([A-Za-z0-9_-]{11})",
        r"youtube\.com/embed/([A-Za-z0-9_-]{11})",
        r"youtube\.com/live/([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


async def _transcript_via_api(video_id: str) -> str | None:
    """Try youtube-transcript-api; return transcript text or None."""
    logger.debug("_transcript_via_api: video_id=%r", video_id)
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        def _fetch() -> list[dict] | None:
            # youtube-transcript-api >= 1.x uses instance methods, not class methods
            api = YouTubeTranscriptApi()

            # 1. Try preferred languages
            try:
                entries = api.fetch(video_id, languages=["ru", "en"])
                logger.info(
                    "[FIX] _transcript_via_api: got preferred-lang transcript video_id=%r",
                    video_id,
                )
                return list(entries)
            except Exception as exc_preferred:
                logger.warning(
                    "[FIX] _transcript_via_api: preferred-lang fetch failed video_id=%r: %s",
                    video_id,
                    exc_preferred,
                )

            # 2. Try any available transcript via list()
            try:
                transcript_list_obj = api.list(video_id)
                available = list(transcript_list_obj)
                logger.debug(
                    "[FIX] _transcript_via_api: available transcripts=%s",
                    [(t.language_code, t.is_generated) for t in available],
                )
                if available:
                    t = available[0]
                    logger.info(
                        "[FIX] _transcript_via_api: fallback transcript"
                        " lang=%r is_generated=%s",
                        t.language_code,
                        t.is_generated,
                    )
                    return list(t.fetch())
                logger.warning(
                    "[FIX] _transcript_via_api: list() returned no transcripts video_id=%r",
                    video_id,
                )
            except Exception as exc_list:
                logger.warning(
                    "[FIX] _transcript_via_api: list() failed video_id=%r: %s",
                    video_id,
                    exc_list,
                )

            return None

        entries = await _run_sync(_fetch)
        if not entries:
            logger.warning("[FIX] _transcript_via_api: no transcripts found video_id=%r", video_id)
            return None
        logger.debug(
            "[FIX] _transcript_via_api: snippet type=%s",
            type(entries[0]).__name__ if entries else "N/A",
        )
        text = " ".join(entry.text for entry in entries)
        logger.info(
            "[FIX] _transcript_via_api: success video_id=%r text_len=%d",
            video_id, len(text),
        )
        return text
    except Exception as exc:
        logger.warning("[FIX] _transcript_via_api: failed video_id=%r: %s", video_id, exc)
        return None


async def _transcript_via_whisper(url: str) -> str | None:
    """Fallback: download audio with yt-dlp then transcribe with local faster-whisper."""
    logger.debug("[FIX] _transcript_via_whisper: url=%r", url)
    try:
        import yt_dlp

        from src.config import settings
        from src.extractors.audio import _get_whisper_model

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "audio.%(ext)s")
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": audio_path,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "128",
                    }
                ],
                "quiet": True,
                "no_warnings": True,
            }
            logger.debug("[FIX] _transcript_via_whisper: downloading audio via yt-dlp url=%r", url)
            await _run_sync(lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]))

            mp3_path = os.path.join(tmpdir, "audio.mp3")
            if not os.path.exists(mp3_path):
                # Find any audio file in tmpdir
                files = os.listdir(tmpdir)
                if not files:
                    logger.warning("[FIX] _transcript_via_whisper: no audio file downloaded")
                    return None
                mp3_path = os.path.join(tmpdir, files[0])

            logger.debug(
                "[FIX] _transcript_via_whisper: transcribing with"
                " faster-whisper audio_path=%r model=%r",
                mp3_path,
                settings.whisper_model,
            )

            def _run_transcription() -> str:
                model = _get_whisper_model()
                segments, info = model.transcribe(mp3_path, beam_size=5)
                text = " ".join(segment.text.strip() for segment in segments)
                logger.debug(
                    "[FIX] _transcript_via_whisper: detected_language=%r", info.language
                )
                return text

            transcript = await _run_sync(_run_transcription)

        logger.info(
            "[FIX] _transcript_via_whisper: success url=%r text_len=%d",
            url,
            len(transcript),
        )
        return transcript
    except Exception as exc:
        logger.error(
            "[FIX] _transcript_via_whisper: failed url=%r: %s", url, exc, exc_info=True
        )
        return None


async def _run_sync(func):  # type: ignore[no-untyped-def]
    """Run a blocking function in a thread executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func)


@register_extractor(ContentType.youtube)
class YouTubeExtractor(BaseExtractor):
    """Extract transcript from a YouTube video."""

    async def extract(self, url: str) -> ExtractedContent:
        logger.info("YouTubeExtractor.extract: url=%r", url)

        video_id = _extract_video_id(url)
        if video_id is None:
            raise ValueError(f"Cannot extract video ID from URL: {url!r}")

        logger.debug("YouTubeExtractor.extract: video_id=%r", video_id)

        # Try subtitle API first
        text = await _transcript_via_api(video_id)

        # Fallback to yt-dlp + faster-whisper
        if text is None:
            logger.warning(
                "[FIX] YouTubeExtractor.extract: transcript API returned nothing, "
                "falling back to yt-dlp + Whisper url=%r",
                url,
            )
            text = await _transcript_via_whisper(url)

        if text is None:
            raise RuntimeError(f"Could not extract transcript for YouTube video: {url!r}")

        original_len = len(text)
        text = _smart_truncate(text, _MAX_TRANSCRIPT_CHARS)
        if len(text) < original_len:
            logger.info(
                "[FIX] YouTubeExtractor.extract: transcript truncated (smart) "
                "original_len=%d final_len=%d url=%r",
                original_len, len(text), url,
            )

        logger.info("YouTubeExtractor.extract: done url=%r text_len=%d", url, len(text))
        return ExtractedContent(
            text=text,
            title=None,
            author=None,
            source_url=url,
            content_type=ContentType.youtube,
        )
