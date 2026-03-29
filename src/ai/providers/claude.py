import logging

from anthropic import AsyncAnthropic

from src.ai.base import HASHTAG_SYSTEM_PROMPT, SUMMARIZE_SYSTEM_PROMPT, BaseAIProvider
from src.extractors.base import ExtractedContent

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

    async def match_hashtags(self, post_text: str, available_hashtags: list[str]) -> list[str]:
        if not available_hashtags:
            return []
        hashtags_list = "\n".join(available_hashtags)
        user_message = f"Доступные хэштеги:\n{hashtags_list}\n\nТекст поста:\n{post_text}"
        logger.debug("[FIX] ClaudeProvider.match_hashtags: model=%s", _MODEL)
        response = await self._client.messages.create(
            model=_MODEL,
            max_tokens=_HASHTAG_MAX_TOKENS,
            system=HASHTAG_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()
        return self._parse_hashtags(raw, available_hashtags)
