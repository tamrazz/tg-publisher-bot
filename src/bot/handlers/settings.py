import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot.keyboards import settings_keyboard
from src.db.models import User, UserRole

logger = logging.getLogger(__name__)
router = Router()


def _is_admin_or_owner(user: User | None) -> bool:
    return user is not None and user.role in (UserRole.owner, UserRole.admin)


@router.message(Command("settings"))
async def handle_settings(message: Message, user: User | None = None) -> None:
    """Show the bot settings menu."""
    telegram_id = message.from_user.id if message.from_user else 0
    logger.debug("[settings] /settings telegram_id=%d", telegram_id)

    if not _is_admin_or_owner(user):
        await message.answer("У вас нет прав для этой команды.")
        return

    await message.answer(
        "⚙️ Настройки бота",
        reply_markup=settings_keyboard(),
    )


@router.message(Command("reset"))
async def handle_reset(message: Message, state: FSMContext, user: User | None = None) -> None:
    """Clear FSM state from any state."""
    telegram_id = message.from_user.id if message.from_user else 0
    logger.debug("[reset] /reset telegram_id=%d", telegram_id)

    if not _is_admin_or_owner(user):
        await message.answer("У вас нет прав для этой команды.")
        return

    await state.clear()
    logger.debug("[reset] state cleared telegram_id=%d", telegram_id)
    await message.answer("✅ Состояние сброшено.")
