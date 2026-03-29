import logging
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram
    bot_token: str
    telegram_channel_id: str

    # AI provider selection: claude | chatgpt | gemini | deepseek (leave empty to disable AI)
    ai_provider: str | None = None

    # AI API keys (only the key for the selected provider is required)
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    deepseek_api_key: str | None = None

    # Database
    database_url: str

    # Local Whisper transcription (faster-whisper)
    # Model sizes: tiny, base, small, medium, large-v2, large-v3
    whisper_model: str = "base"
    # Device: cpu | cuda (use cuda if GPU is available)
    whisper_device: str = "cpu"

    # Optional integrations
    github_token: str | None = None

    # Auth — comma-separated Telegram user IDs, e.g. "123456,789012"
    owner_ids: str = ""

    # Logging
    log_level: str = "INFO"

    @property
    def owner_id_list(self) -> list[int]:
        """Parse OWNER_IDS into a list of integers."""
        if not self.owner_ids.strip():
            return []
        try:
            return [int(uid.strip()) for uid in self.owner_ids.split(",") if uid.strip()]
        except ValueError as exc:
            logger.error("Failed to parse OWNER_IDS=%r: %s", self.owner_ids, exc)
            return []


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings instance. Loaded lazily on first call."""
    logger.debug("Loading settings from environment")
    return Settings()  # type: ignore[call-arg]


# Module-level proxy — accessed as `settings.bot_token` etc.
# Instantiation is deferred until first attribute access.
class _SettingsProxy:
    """Transparent proxy that forwards attribute access to get_settings()."""

    def __getattr__(self, name: str):  # type: ignore[override]
        return getattr(get_settings(), name)

    def __repr__(self) -> str:
        return repr(get_settings())


settings: Settings = _SettingsProxy()  # type: ignore[assignment]
