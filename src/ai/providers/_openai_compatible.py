import logging
from typing import TYPE_CHECKING

from openai import AsyncOpenAI

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

_SUMMARIZE_MAX_TOKENS = 512
_HASHTAG_MAX_TOKENS = 128


class OpenAICompatibleProvider(BaseAIProvider):
    """Shared base for providers that use the OpenAI chat completions API format."""

    _model: str
    _client: AsyncOpenAI

    async def summarize(self, content: ExtractedContent) -> str:
        logger.debug("[FIX] %s.summarize: model=%s", self.__class__.__name__, self._model)
        user_message = self._build_summarize_user_message(content)
        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=_SUMMARIZE_MAX_TOKENS,
            messages=[
                {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )
        result = (response.choices[0].message.content or "").strip()
        logger.debug(
            "[FIX] %s.summarize: done input_tokens=%d output_tokens=%d",
            self.__class__.__name__,
            response.usage.prompt_tokens if response.usage else 0,
            response.usage.completion_tokens if response.usage else 0,
        )
        return result

    async def match_hashtags(
        self, post_text: str, available_hashtags: list["Hashtag"]
    ) -> list[str]:
        if not available_hashtags:
            return []
        user_message = self._build_hashtag_user_message(post_text, available_hashtags)
        logger.debug(
            "[FIX] %s.match_hashtags: model=%s input_tags=%d",
            self.__class__.__name__,
            self._model,
            len(available_hashtags),
        )
        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=_HASHTAG_MAX_TOKENS,
            messages=[
                {"role": "system", "content": HASHTAG_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )
        raw = (response.choices[0].message.content or "").strip()
        return self._parse_hashtags(raw, available_hashtags)

    async def generate_hashtags(self, post_text: str, count: int) -> list[str]:
        if count <= 0:
            return []
        logger.debug(
            "[FIX] %s.generate_hashtags: model=%s count=%d",
            self.__class__.__name__,
            self._model,
            count,
        )
        user_message = f"Придумай {count} хэштег(а/ов) для следующего поста:\n\n{post_text}"
        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=_HASHTAG_MAX_TOKENS,
            messages=[
                {"role": "system", "content": GENERATE_HASHTAGS_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )
        raw = (response.choices[0].message.content or "").strip()
        result = self._parse_generated_hashtags(raw, count)
        logger.debug(
            "[FIX] %s.generate_hashtags: generated=%s", self.__class__.__name__, result
        )
        return result
