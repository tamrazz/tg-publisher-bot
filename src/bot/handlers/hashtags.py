import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot.states import HashtagCreationStates
from src.db.models import User, UserRole
from src.db.session import AsyncSessionLocal
from src.services.hashtags import add_hashtag, get_all_hashtags, remove_hashtag

logger = logging.getLogger(__name__)
router = Router()


def _is_admin_or_owner(user: User | None) -> bool:
    return user is not None and user.role in (UserRole.owner, UserRole.admin)


@router.message(Command("add_hashtag"))
async def handle_add_hashtag(message: Message, state: FSMContext, user: User | None = None) -> None:
    """Start hashtag creation flow."""
    telegram_id = message.from_user.id if message.from_user else 0
    logger.debug("handle_add_hashtag: telegram_id=%d", telegram_id)

    if not _is_admin_or_owner(user):
        await message.answer("У вас нет прав для этой команды.")
        return

    await state.set_state(HashtagCreationStates.waiting_for_tag)
    await message.answer(
        "Введите хэштег (например: <code>#tools</code> или <code>tools</code>):",
        parse_mode="HTML",
    )


@router.message(HashtagCreationStates.waiting_for_tag, F.text)
async def handle_hashtag_tag_input(
    message: Message, state: FSMContext, user: User | None = None
) -> None:
    """Receive the tag string and ask for description."""
    if not _is_admin_or_owner(user):
        await state.clear()
        return

    tag = (message.text or "").strip()
    if not tag:
        await message.answer("Хэштег не может быть пустым. Введите снова:")
        return

    await state.update_data(new_tag=tag)
    await state.set_state(HashtagCreationStates.waiting_for_description)
    await message.answer(
        f"Хэштег: <code>{tag}</code>\n\nВведите описание (или /skip чтобы пропустить):",
        parse_mode="HTML",
    )


@router.message(HashtagCreationStates.waiting_for_description)
async def handle_hashtag_description_input(
    message: Message, state: FSMContext, user: User | None = None
) -> None:
    """Receive description and create the hashtag."""
    if not _is_admin_or_owner(user):
        await state.clear()
        return

    data = await state.get_data()
    tag: str = data.get("new_tag", "")
    await state.clear()

    text = (message.text or "").strip()
    description = None if text == "/skip" else text
    telegram_id = message.from_user.id if message.from_user else 0

    logger.info(
        "handle_hashtag_description_input: tag=%r description=%r telegram_id=%d",
        tag,
        description,
        telegram_id,
    )

    async with AsyncSessionLocal() as session:
        hashtag, created = await add_hashtag(
            session,
            tag=tag,
            created_by=telegram_id,
            description=description,
        )
        await session.commit()

    if created:
        logger.info(
            "handle_hashtag_description_input: created hashtag tag=%r id=%d",
            tag,
            hashtag.id,
        )
        await message.answer(
            f"✅ Хэштег <code>{hashtag.tag}</code> добавлен.",
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"⚠️ Хэштег <code>{hashtag.tag}</code> уже существует.",
            parse_mode="HTML",
        )


@router.message(Command("list_hashtags"))
async def handle_list_hashtags(message: Message, user: User | None = None) -> None:
    """List all hashtags."""
    telegram_id = message.from_user.id if message.from_user else 0
    logger.debug("handle_list_hashtags: telegram_id=%d", telegram_id)

    if not _is_admin_or_owner(user):
        await message.answer("У вас нет прав для этой команды.")
        return

    async with AsyncSessionLocal() as session:
        hashtags = await get_all_hashtags(session)

    if not hashtags:
        await message.answer("Список хэштегов пуст.")
        return

    lines = []
    for h in hashtags:
        line = f"• <code>{h.tag}</code>"
        if h.description:
            line += f" — {h.description}"
        lines.append(line)

    logger.debug("handle_list_hashtags: returning %d hashtags", len(hashtags))
    await message.answer(
        "<b>Хэштеги:</b>\n" + "\n".join(lines),
        parse_mode="HTML",
    )


@router.message(Command("delete_hashtag"))
async def handle_delete_hashtag(message: Message, user: User | None = None) -> None:
    """
    /delete_hashtag <tag>
    Delete a hashtag by name.
    """
    telegram_id = message.from_user.id if message.from_user else 0
    logger.debug("handle_delete_hashtag: telegram_id=%d", telegram_id)

    if not _is_admin_or_owner(user):
        await message.answer("У вас нет прав для этой команды.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /delete_hashtag <тег>")
        return

    tag = parts[1].strip()
    logger.info("handle_delete_hashtag: tag=%r telegram_id=%d", tag, telegram_id)

    async with AsyncSessionLocal() as session:
        deleted = await remove_hashtag(session, tag)
        await session.commit()

    if deleted:
        logger.info("handle_delete_hashtag: deleted tag=%r", tag)
        tag_display = tag if tag.startswith("#") else f"#{tag}"
        await message.answer(
            f"✅ Хэштег <code>{tag_display}</code> удалён.",
            parse_mode="HTML",
        )
    else:
        await message.answer(f"❌ Хэштег <code>{tag}</code> не найден.", parse_mode="HTML")
