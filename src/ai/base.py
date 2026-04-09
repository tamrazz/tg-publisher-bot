import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from src.extractors.base import ExtractedContent

if TYPE_CHECKING:
    from src.db.models import Hashtag

_MAX_HASHTAGS = 5

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
⚠️ Почему вайбкодеры не заменят программистов — как LLM установили заражённый \
пакет в тысячах проектов.
"""

HASHTAG_SYSTEM_PROMPT = """\
Ты — ассистент, который подбирает хэштеги для Telegram-постов.
Тебе дадут список доступных хэштегов с описаниями и текст поста.
Используй описания, чтобы понять, когда применять каждый хэштег.
Выбери от 2 до 5 наиболее подходящих хэштегов из списка.
Выведи только хэштеги через пробел, без пояснений. Например: #tools #ai #python
Если ни один хэштег не подходит, выведи пустую строку.
"""

GENERATE_HASHTAGS_SYSTEM_PROMPT = """\
Ты — ассистент, который придумывает релевантные хэштеги для Telegram-постов.
Тебе дадут текст поста и количество хэштегов, которые нужно сгенерировать.

Придумай ровно столько хэштегов, сколько указано. Ставь приоритет на конкретные \
сущности из материала:
- Названия инструментов, библиотек, фреймворков: #Python, #Docker, #LangChain, #Whisper
- Бренды и компании: #OpenAI, #Google, #Apple, #Anthropic
- Технологии и концепции: #LLM, #RAG, #MachineLearning, #ComputerVision
- Известные личности: #ElonMusk, #SamAltman, #ИльяСуцкевер

Избегай расплывчатых описательных хэштегов вроде #высокотехнологичныепродукты, \
#интересноевидео или #полезнаяинформация.
Хороший хэштег — конкретный: по нему можно найти несколько связанных материалов на одну тему.

Хэштеги на русском или английском языке, без пробелов, только буквы/цифры/подчёркивание.
Выведи только хэштеги через пробел, без пояснений. Например: #Python #OpenAI #LLM
"""


class BaseAIProvider(ABC):
    """Abstract base class for AI providers used for summarization and hashtag matching."""

    @abstractmethod
    async def summarize(self, content: ExtractedContent) -> str:
        """Generate a 2-3 sentence Russian announcement for content."""
        ...

    @abstractmethod
    async def match_hashtags(
        self, post_text: str, available_hashtags: list["Hashtag"]
    ) -> list[str]:
        """Pick 2-5 relevant hashtags from available_hashtags for post_text."""
        ...

    @abstractmethod
    async def generate_hashtags(self, post_text: str, count: int) -> list[str]:
        """Generate *count* topical hashtags for post_text (not from DB)."""
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

    def _build_hashtag_user_message(self, post_text: str, hashtags: list["Hashtag"]) -> str:
        # Tags are stored without # in the DB; add # for the AI prompt so it sees
        # the canonical Telegram hashtag format (e.g. "#python — описание")
        lines = []
        for h in hashtags:
            if h.description:
                lines.append(f"#{h.tag} — {h.description}")
            else:
                lines.append(f"#{h.tag}")
        hashtags_list = "\n".join(lines)
        return f"Доступные хэштеги:\n{hashtags_list}\n\nТекст поста:\n{post_text}"

    def _parse_generated_hashtags(self, raw: str, count: int) -> list[str]:
        """Parse AI-generated hashtags (no DB filter). Returns tags without '#'."""
        tokens = re.findall(r"#\S+", raw)
        result = []
        seen: set[str] = set()
        for token in tokens:
            tag = token.lstrip("#").lower()
            if tag and tag not in seen:
                seen.add(tag)
                result.append(tag)
            if len(result) >= count:
                break
        return result

    def _parse_hashtags(self, raw: str, available: list["Hashtag"]) -> list[str]:
        # AI returns "#tag" format; DB stores without "#" — strip "#" before comparing
        tokens = re.findall(r"#\S+", raw)
        available_set = {h.tag.lower() for h in available}
        result = []
        for token in tokens:
            tag_without_hash = token.lstrip("#").lower()
            if tag_without_hash in available_set:
                result.append(tag_without_hash)  # return without # (DB format)
            if len(result) >= _MAX_HASHTAGS:
                break
        return result
