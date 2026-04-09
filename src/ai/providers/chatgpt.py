from openai import AsyncOpenAI

from src.ai.providers._openai_compatible import OpenAICompatibleProvider


class ChatGPTProvider(OpenAICompatibleProvider):
    _model = "gpt-4o-mini"

    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
