import logging
from typing import TYPE_CHECKING

from anthropic import AsyncAnthropic

from src.ai.base import (
    GENERATE_HASHTAGS_SYSTEM_PROMPT,
    HASHTAG_SYSTEM_PROMPT,
    SUMMARIZE_SYSTEM_PROMPT,
    BaseAIProvider,
)
from src.extractors.base import ExtractedContent

if TYPE_CHECKING:
    from src.db.models import Hashtag

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_SUMMARIZE_MAX_TOKENS = 512
_HASHTAG_MAX_TOKENS = 128


class ClaudeProvider(BaseAIProvider):
    def __init__(self, api_key: str) -> None:
        self._client = AsyncAnthropic(api_key=api_key)

    async def summarize(self, content: ExtractedContent) -> str:
        logger.debug("[FIX] ClaudeProvider.summarize: model=%s", _MODEL)
        user_message = self._build_summarize_user_message(content)
        response = await self._client.messages.create(
            model=_MODEL,
            max_tokens=_SUMMARIZE_MAX_TOKENS,
            system=SUMMARIZE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        result = response.content[0].text.strip()
        logger.debug(
            "[FIX] ClaudeProvider.summarize: done input_tokens=%d output_tokens=%d",
            response.usage.input_tokens,
            response.usage.output_tokens,
        )
        return result

    async def match_hashtags(
        self, post_text: str, available_hashtags: list["Hashtag"]
    ) -> list[str]:
        if not available_hashtags:
            return []
        user_message = self._build_hashtag_user_message(post_text, available_hashtags)
        logger.debug(
            "[FIX] ClaudeProvider.match_hashtags: model=%s input_tags=%d",
            _MODEL,
            len(available_hashtags),
        )
        response = await self._client.messages.create(
            model=_MODEL,
            max_tokens=_HASHTAG_MAX_TOKENS,
            system=HASHTAG_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()
        return self._parse_hashtags(raw, available_hashtags)

    async def generate_hashtags(self, post_text: str, count: int) -> list[str]:
        if count <= 0:
            return []
        logger.debug("[FIX] ClaudeProvider.generate_hashtags: model=%s count=%d", _MODEL, count)
        user_message = f"Придумай {count} хэштег(а/ов) для следующего поста:\n\n{post_text}"
        response = await self._client.messages.create(
            model=_MODEL,
            max_tokens=_HASHTAG_MAX_TOKENS,
            system=GENERATE_HASHTAGS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()
        result = self._parse_generated_hashtags(raw, count)
        logger.debug("[FIX] ClaudeProvider.generate_hashtags: generated=%s", result)
        return result
