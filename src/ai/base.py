import re
from abc import ABC, abstractmethod

from src.extractors.base import ExtractedContent

_MAX_HASHTAGS = 3

SUMMARIZE_SYSTEM_PROMPT = """\
Ты — редактор Telegram-канала. Напиши интригующий анонс на русском языке, \
который заставит пользователя кликнуть и посмотреть материал.

Требования:
- Не более 3 коротких предложений
- Стиль: интрига, неожиданный факт или провокационный вопрос — зацепи читателя, не раскрывай всё
- Анонс ВСЕГДА на русском языке — даже если источник на иностранном языке
- Без вводных слов («В этом видео...», «Автор рассказывает...», «Статья о...»)
- Эмодзи только в начале или в конце анонса, не в середине текста (не более 2 эмодзи)
- Без хэштегов, без копирайта

Пример хорошего анонса:
⚠️ Почему вайбкодеры не заменят программистов — как LLM установили заражённый пакет в тысячах проектов.
"""

HASHTAG_SYSTEM_PROMPT = """\
Ты — ассистент, который подбирает хэштеги для Telegram-постов.
Тебе дадут список доступных хэштегов и текст поста.
Выбери от 1 до 3 наиболее подходящих хэштегов из списка.
Выведи только хэштеги через пробел, без пояснений. Например: #tools #ai #python
Если ни один хэштег не подходит, выведи пустую строку.
"""


class BaseAIProvider(ABC):
    """Abstract base class for AI providers used for summarization and hashtag matching."""

    @abstractmethod
    async def summarize(self, content: ExtractedContent) -> str:
        """Generate a 2-3 sentence Russian announcement for content."""
        ...

    @abstractmethod
    async def match_hashtags(self, post_text: str, available_hashtags: list[str]) -> list[str]:
        """Pick 1-3 relevant hashtags from available_hashtags for post_text."""
        ...

    def _build_summarize_user_message(self, content: ExtractedContent) -> str:
        parts = []
        if content.title:
            parts.append(f"Заголовок: {content.title}")
        if content.author:
            parts.append(f"Автор/источник: {content.author}")
        parts.append(f"URL: {content.source_url}")
        parts.append(f"\nТекст материала:\n{content.text}")
        return "\n".join(parts)

    def _parse_hashtags(self, raw: str, available: list[str]) -> list[str]:
        tokens = re.findall(r"#\S+", raw)
        available_set = {tag.lower() for tag in available}
        result = []
        for token in tokens:
            if token.lower() in available_set:
                result.append(token)
            if len(result) >= _MAX_HASHTAGS:
                break
        return result
