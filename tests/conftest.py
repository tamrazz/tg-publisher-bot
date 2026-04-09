import os

import pytest

# ---------------------------------------------------------------------------
# Provide dummy env vars so Settings can always be instantiated during tests.
# Tests that need specific values should use monkeypatch.setenv.
# ---------------------------------------------------------------------------
_DUMMY_ENV = {
    "BOT_TOKEN": "0000000000:AAFakeTokenForTestsAAAAAAAAAAAAAAAAA",
    "TELEGRAM_CHANNEL_ID": "-1001234567890",
    "AI_PROVIDER": "claude",
    "ANTHROPIC_API_KEY": "sk-ant-fake-key",
    "OPENAI_API_KEY": "sk-fake-openai-key",
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
    "OWNER_IDS": "123456",
    "LOG_LEVEL": "DEBUG",
}

for _k, _v in _DUMMY_ENV.items():
    os.environ.setdefault(_k, _v)


@pytest.fixture(autouse=True)
def reset_settings_cache():
    """Clear lru_cache on get_settings() and get_ai_provider() between tests."""
    from src.ai.factory import get_ai_provider
    from src.config import get_settings

    get_settings.cache_clear()
    get_ai_provider.cache_clear()
    yield
    get_settings.cache_clear()
    get_ai_provider.cache_clear()
