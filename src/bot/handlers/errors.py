import html
import logging

from aiogram import Bot, Router
from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)
router = Router()


@router.errors()
async def global_error_handler(event: ErrorEvent, bot: Bot) -> bool:
    """Catch any unhandled exception and report it to the user who triggered the update."""
    exc = event.exception
    update = event.update

    logger.error(
        "Unhandled exception in update_id=%s: %s",
        update.update_id,
        exc,
        exc_info=exc,
    )

    chat_id: int | None = None
    if update.message:
        chat_id = update.message.chat.id
    elif update.callback_query and update.callback_query.message:
        chat_id = update.callback_query.message.chat.id

    if chat_id is not None:
        await bot.send_message(
            chat_id=chat_id,
            text=f"❌ Произошла ошибка:\n<code>{html.escape(str(exc))}</code>",
            parse_mode="HTML",
        )

    return True  # suppress — prevents aiogram from re-raising
