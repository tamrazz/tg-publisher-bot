import logging

from openai import AsyncOpenAI

from src.ai.base import HASHTAG_SYSTEM_PROMPT, SUMMARIZE_SYSTEM_PROMPT, BaseAIProvider
from src.extractors.base import ExtractedContent

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

    async def match_hashtags(self, post_text: str, available_hashtags: list[str]) -> list[str]:
        if not available_hashtags:
            return []
        hashtags_list = "\n".join(available_hashtags)
        user_message = f"Доступные хэштеги:\n{hashtags_list}\n\nТекст поста:\n{post_text}"
        logger.debug("[FIX] %s.match_hashtags: model=%s", self.__class__.__name__, self._model)
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
