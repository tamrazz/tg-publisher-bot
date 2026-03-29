import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.db.models import User, UserRole
from src.db.session import AsyncSessionLocal
from src.services.users import add_admin, remove_admin

logger = logging.getLogger(__name__)
router = Router()


def _require_owner(user: User | None) -> bool:
    return user is not None and user.role == UserRole.owner


@router.message(Command("add_admin"))
async def handle_add_admin(message: Message, user: User | None = None) -> None:
    """
    /add_admin <telegram_id>
    Owner-only command to grant admin access to a Telegram user ID.
    """
    logger.debug(
        "handle_add_admin: from telegram_id=%s",
        message.from_user.id if message.from_user else "unknown",
    )

    if not _require_owner(user):
        logger.warning(
            "handle_add_admin: permission denied for telegram_id=%s",
            message.from_user.id if message.from_user else "unknown",
        )
        await message.answer("У вас нет прав для этой команды.")
        return

    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].lstrip("-").isdigit():
        await message.answer("Использование: /add_admin <telegram_id>")
        return

    target_id = int(parts[1])
    logger.info("handle_add_admin: adding admin telegram_id=%d", target_id)

    async with AsyncSessionLocal() as session:
        updated = await add_admin(session, target_id)
        await session.commit()

    if updated is None:
        await message.answer(f"Пользователь {target_id} не найден или является владельцем.")
    else:
        logger.info("handle_add_admin: telegram_id=%d added as admin", target_id)
        await message.answer(f"Пользователь {target_id} назначен администратором.")


@router.message(Command("remove_admin"))
async def handle_remove_admin(message: Message, user: User | None = None) -> None:
    """
    /remove_admin <telegram_id>
    Owner-only command to revoke admin access.
    """
    logger.debug(
        "handle_remove_admin: from telegram_id=%s",
        message.from_user.id if message.from_user else "unknown",
    )

    if not _require_owner(user):
        logger.warning(
            "handle_remove_admin: permission denied for telegram_id=%s",
            message.from_user.id if message.from_user else "unknown",
        )
        await message.answer("У вас нет прав для этой команды.")
        return

    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].lstrip("-").isdigit():
        await message.answer("Использование: /remove_admin <telegram_id>")
        return

    target_id = int(parts[1])
    logger.info("handle_remove_admin: removing admin telegram_id=%d", target_id)

    async with AsyncSessionLocal() as session:
        removed = await remove_admin(session, target_id)
        await session.commit()

    if removed:
        logger.info("handle_remove_admin: telegram_id=%d removed", target_id)
        await message.answer(f"Пользователь {target_id} удалён из администраторов.")
    else:
        await message.answer(f"Пользователь {target_id} не найден или является владельцем.")
