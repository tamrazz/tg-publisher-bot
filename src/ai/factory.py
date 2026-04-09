import logging
from functools import lru_cache

from src.ai.base import BaseAIProvider
from src.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_ai_provider() -> BaseAIProvider | None:
    """
    Return the configured AI provider instance, or None if not configured.

    The provider is selected by AI_PROVIDER in .env:
      claude    → ClaudeProvider    (requires ANTHROPIC_API_KEY)
      chatgpt   → ChatGPTProvider   (requires OPENAI_API_KEY)
      gemini    → GeminiProvider    (requires GEMINI_API_KEY)
      deepseek  → DeepSeekProvider  (requires DEEPSEEK_API_KEY)

    Returns None if AI_PROVIDER is unset, unknown, or the required API key is missing.
    """
    provider_name = (settings.ai_provider or "").strip().lower()
    logger.info("[FIX] get_ai_provider: ai_provider=%r", provider_name)

    if not provider_name:
        logger.warning("[FIX] get_ai_provider: AI_PROVIDER not set — AI disabled")
        return None

    if provider_name == "claude":
        if not settings.anthropic_api_key:
            logger.error("[FIX] get_ai_provider: ANTHROPIC_API_KEY required for claude provider")
            return None
        from src.ai.providers.claude import ClaudeProvider

        provider = ClaudeProvider(api_key=settings.anthropic_api_key)

    elif provider_name == "chatgpt":
        if not settings.openai_api_key:
            logger.error("[FIX] get_ai_provider: OPENAI_API_KEY required for chatgpt provider")
            return None
        from src.ai.providers.chatgpt import ChatGPTProvider

        provider = ChatGPTProvider(api_key=settings.openai_api_key)

    elif provider_name == "gemini":
        if not settings.gemini_api_key:
            logger.error("[FIX] get_ai_provider: GEMINI_API_KEY required for gemini provider")
            return None
        from src.ai.providers.gemini import GeminiProvider

        provider = GeminiProvider(api_key=settings.gemini_api_key)

    elif provider_name == "deepseek":
        if not settings.deepseek_api_key:
            logger.error("[FIX] get_ai_provider: DEEPSEEK_API_KEY required for deepseek provider")
            return None
        from src.ai.providers.deepseek import DeepSeekProvider

        provider = DeepSeekProvider(api_key=settings.deepseek_api_key)

    elif provider_name == "groq":
        if not settings.groq_api_key:
            logger.error("[FIX] get_ai_provider: GROQ_API_KEY required for groq provider")
            return None
        from src.ai.providers.groq import GroqProvider

        logger.info("[FIX] get_ai_provider: using Groq model=llama-3.3-70b-versatile")
        provider = GroqProvider(api_key=settings.groq_api_key)

    else:
        logger.error("[FIX] get_ai_provider: unknown provider=%r — AI disabled", provider_name)
        return None

    logger.info("[FIX] get_ai_provider: initialized provider=%s", type(provider).__name__)
    return provider
