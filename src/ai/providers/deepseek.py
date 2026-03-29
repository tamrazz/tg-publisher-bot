from openai import AsyncOpenAI

from src.ai.providers._openai_compatible import OpenAICompatibleProvider

_DEEPSEEK_BASE_URL = "https://api.deepseek.com"


class DeepSeekProvider(OpenAICompatibleProvider):
    _model = "deepseek-chat"

    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=_DEEPSEEK_BASE_URL)
