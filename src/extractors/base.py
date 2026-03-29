import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.extractors.detector import ContentType

logger = logging.getLogger(__name__)


@dataclass
class ExtractedContent:
    text: str
    title: str | None
    author: str | None
    source_url: str
    content_type: ContentType


class BaseExtractor(ABC):
    """Abstract base for all content extractors."""

    @abstractmethod
    async def extract(self, url: str) -> ExtractedContent:
        """Extract content from *url* and return an ExtractedContent instance."""
        ...


# ---------------------------------------------------------------------------
# Extractor registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[ContentType, type[BaseExtractor]] = {}


def register_extractor(content_type: ContentType) -> "type[BaseExtractor]":
    """Class decorator that registers an extractor for *content_type*."""

    def decorator(cls: type[BaseExtractor]) -> type[BaseExtractor]:
        logger.debug("Registering extractor %s for content_type=%s", cls.__name__, content_type)
        _REGISTRY[content_type] = cls
        return cls

    return decorator  # type: ignore[return-value]


def get_extractor(content_type: ContentType) -> BaseExtractor:
    """Instantiate and return the registered extractor for *content_type*."""
    cls = _REGISTRY.get(content_type)
    if cls is None:
        raise ValueError(f"No extractor registered for content_type={content_type!r}")
    logger.debug("get_extractor: returning %s for content_type=%s", cls.__name__, content_type)
    return cls()
