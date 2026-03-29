import logging
import os
import tempfile

import httpx

from src.config import settings
from src.extractors.base import BaseExtractor, ExtractedContent, register_extractor
from src.extractors.detector import ContentType

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 60.0
_MAX_FILE_SIZE = 200 * 1024 * 1024  # 200 MB local limit
_CHUNK_SIZE = 64 * 1024  # 64 KB download chunks

# Module-level model singleton — loaded on first use
_whisper_model = None


def _get_whisper_model():
    """Return the cached faster-whisper model, loading it on first call."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        logger.info(
            "[FIX] Loading faster-whisper model=%r device=%r",
            settings.whisper_model,
            settings.whisper_device,
        )
        _whisper_model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type="int8",
        )
        logger.info("[FIX] faster-whisper model loaded successfully")
    return _whisper_model


@register_extractor(ContentType.audio)
class AudioExtractor(BaseExtractor):
    """Download audio from a direct URL and transcribe via local faster-whisper."""

    async def extract(self, url: str) -> ExtractedContent:
        logger.info("AudioExtractor.extract: url=%r", url)

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = await _download_audio(url, tmpdir)
            transcript = await _transcribe(audio_path)

        logger.info(
            "AudioExtractor.extract: done url=%r transcript_len=%d",
            url,
            len(transcript),
        )
        return ExtractedContent(
            text=transcript,
            title=None,
            author=None,
            source_url=url,
            content_type=ContentType.audio,
        )


async def _download_audio(url: str, tmpdir: str) -> str:
    """Stream-download audio to a temp file and return its path."""
    logger.debug("_download_audio: url=%r", url)

    filename = url.split("?")[0].rsplit("/", 1)[-1] or "audio.mp3"
    dest = os.path.join(tmpdir, filename)

    async with httpx.AsyncClient(follow_redirects=True, timeout=_REQUEST_TIMEOUT) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            content_length = int(response.headers.get("content-length", 0))
            logger.debug("_download_audio: content_length=%d url=%r", content_length, url)
            if content_length > _MAX_FILE_SIZE:
                raise ValueError(
                    f"Audio file too large ({content_length} bytes > {_MAX_FILE_SIZE})"
                )

            total = 0
            with open(dest, "wb") as f:
                async for chunk in response.aiter_bytes(_CHUNK_SIZE):
                    total += len(chunk)
                    if total > _MAX_FILE_SIZE:
                        raise ValueError(f"Audio file exceeds {_MAX_FILE_SIZE} bytes limit")
                    f.write(chunk)

    logger.debug("_download_audio: saved %d bytes to %r", total, dest)
    return dest


async def _transcribe(audio_path: str) -> str:
    """Transcribe *audio_path* using local faster-whisper model."""
    import asyncio

    logger.debug("[FIX] _transcribe: audio_path=%r", audio_path)

    def _run_transcription() -> str:
        model = _get_whisper_model()
        segments, info = model.transcribe(audio_path, beam_size=5)
        text = " ".join(segment.text.strip() for segment in segments)
        logger.debug(
            "[FIX] _transcribe: detected_language=%r audio_path=%r",
            info.language,
            audio_path,
        )
        return text

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _run_transcription)
    logger.debug("[FIX] _transcribe: done audio_path=%r transcript_len=%d", audio_path, len(result))
    return result
