from openai import AsyncOpenAI

from src.ai.providers._openai_compatible import OpenAICompatibleProvider

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"


class GroqProvider(OpenAICompatibleProvider):
    _model = _GROQ_DEFAULT_MODEL

    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=_GROQ_BASE_URL)
