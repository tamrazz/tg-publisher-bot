from openai import AsyncOpenAI

from src.ai.providers._openai_compatible import OpenAICompatibleProvider

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


class GeminiProvider(OpenAICompatibleProvider):
    _model = "gemini-2.0-flash"

    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=_GEMINI_BASE_URL)
