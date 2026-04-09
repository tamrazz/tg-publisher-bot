"""
Hashtag management FSM handlers.

Flow:
  /settings → [🏷 Хештеги] → hashtag list
  → [➕ Добавить новый] or [existing hashtag] → action_keyboard
  → entering_tag → selecting_category (→ entering_category_name) → entering_description → confirming
"""
import logging
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards import (
    category_select_keyboard,
    hashtag_action_keyboard,
    hashtag_confirm_keyboard,
    hashtag_list_keyboard,
)
from src.bot.states import HashtagMgmtStates
from src.db.models import User, UserRole
from src.db.repository import (
    create_category,
    create_hashtag,
    delete_hashtag_by_id,
    get_category_by_id,
    get_hashtag_by_id,
    list_categories,
    list_hashtags,
    update_hashtag,
)
from src.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)
router = Router()

_HASHTAG_RE = re.compile(r"^#?[a-zA-Zа-яА-ЯёЁ0-9_]{2,}$")


def _normalize_tag(raw: str) -> str:
    """Strip leading # and whitespace — tags are stored without # in the DB."""
    return raw.strip().lstrip("#")


def _is_admin_or_owner(user: User | None) -> bool:
    return user is not None and user.role in (UserRole.owner, UserRole.admin)


def _format_category_label(cat_name: str, is_required: bool) -> str:
    return f"⚠️ {cat_name} (обязательная)" if is_required else cat_name


# ---------------------------------------------------------------------------
# Hashtag list
# ---------------------------------------------------------------------------


@router.callback_query(F.data == "settings:hashtags")
async def cb_settings_hashtags(
    callback: CallbackQuery, user: User | None = None
) -> None:
    """Show the hashtag list."""
    telegram_id = callback.from_user.id if callback.from_user else 0
    logger.debug("[hashtag_mgmt] settings:hashtags telegram_id=%d", telegram_id)

    if not _is_admin_or_owner(user):
        await callback.answer("Нет прав.", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        hashtags = await list_hashtags(session)

    logger.debug("[hashtag_mgmt] settings:hashtags count=%d", len(hashtags))
    await callback.message.answer(
        f"🏷 <b>Хештеги</b> ({len(hashtags)})",
        reply_markup=hashtag_list_keyboard(hashtags),
        parse_mode="HTML",
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# New hashtag creation
# ---------------------------------------------------------------------------


@router.callback_query(F.data == "ht:new")
async def cb_ht_new(callback: CallbackQuery, state: FSMContext, user: User | None = None) -> None:
    """Start creating a new hashtag — ask for the tag."""
    telegram_id = callback.from_user.id if callback.from_user else 0
    logger.debug("[hashtag_mgmt] ht:new telegram_id=%d", telegram_id)

    if not _is_admin_or_owner(user):
        await callback.answer("Нет прав.", show_alert=True)
        return

    await state.set_state(HashtagMgmtStates.entering_tag)
    await state.update_data(hashtag_id=None, original_data=None)
    await callback.message.answer(
        "Введите хештег (например: <code>#python</code>):",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(HashtagMgmtStates.entering_tag, F.text)
async def msg_entering_tag(
    message: Message, state: FSMContext, user: User | None = None
) -> None:
    """Validate tag format and proceed to category selection."""
    if not _is_admin_or_owner(user):
        await state.clear()
        return

    tag = (message.text or "").strip()
    telegram_id = message.from_user.id if message.from_user else 0
    logger.debug("[hashtag_mgmt] entering_tag telegram_id=%d tag=%r", telegram_id, tag)

    if not _HASHTAG_RE.match(tag):
        await message.answer(
            "❌ Неверный формат. Хештег должен содержать только буквы, цифры и <code>_</code> "
            "(минимум 2 символа, <code>#</code> необязателен). Попробуйте снова:",
            parse_mode="HTML",
        )
        return

    normalized = _normalize_tag(tag)
    logger.debug(
        "[hashtag_mgmt] entering_tag: raw=%r normalized=%r", tag, normalized
    )
    await state.update_data(tag=normalized)

    async with AsyncSessionLocal() as session:
        categories = await list_categories(session)

    logger.debug("[hashtag_mgmt] entering_tag: tag=%r → selecting_category", tag)
    await state.set_state(HashtagMgmtStates.selecting_category)
    await message.answer(
        "Выберите категорию хештега:",
        reply_markup=category_select_keyboard(categories),
    )


# ---------------------------------------------------------------------------
# Category selection
# ---------------------------------------------------------------------------


@router.callback_query(F.data.startswith("cat:pick:"))
async def cb_cat_pick(
    callback: CallbackQuery, state: FSMContext, user: User | None = None
) -> None:
    """Save selected category and ask for description."""
    if not _is_admin_or_owner(user):
        await callback.answer("Нет прав.", show_alert=True)
        return

    category_id = int(callback.data.split(":")[2])
    logger.debug("[hashtag_mgmt] cat:pick category_id=%d", category_id)

    await state.update_data(category_id=category_id)
    await state.set_state(HashtagMgmtStates.entering_description)
    await callback.message.answer(
        "Введите описание хештега (по нему AI решает когда его применять):"
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Category creation
# ---------------------------------------------------------------------------


@router.callback_query(F.data == "cat:new")
async def cb_cat_new(
    callback: CallbackQuery, state: FSMContext, user: User | None = None
) -> None:
    """Ask for a new category name."""
    if not _is_admin_or_owner(user):
        await callback.answer("Нет прав.", show_alert=True)
        return

    logger.debug("[hashtag_mgmt] cat:new — entering_category_name")
    await state.set_state(HashtagMgmtStates.entering_category_name)
    await callback.message.answer(
        "Введите название категории.\n"
        "Добавьте <code>!</code> в начало чтобы сделать её обязательной "
        "(например: <code>!Тематика</code>):",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(HashtagMgmtStates.entering_category_name, F.text)
async def msg_entering_category_name(
    message: Message, state: FSMContext, user: User | None = None
) -> None:
    """Create the new category and return to category selection."""
    if not _is_admin_or_owner(user):
        await state.clear()
        return

    raw = (message.text or "").strip()
    is_required = raw.startswith("!")
    name = raw.lstrip("!").strip()
    logger.debug(
        "[hashtag_mgmt] entering_category_name name=%r is_required=%s", name, is_required
    )

    if not name:
        await message.answer("Название не может быть пустым. Введите снова:")
        return

    async with AsyncSessionLocal() as session:
        category = await create_category(session, name=name, is_required=is_required)
        await session.commit()

    async with AsyncSessionLocal() as session:
        categories = await list_categories(session)

    logger.debug("[hashtag_mgmt] created category id=%d name=%r", category.id, name)
    await state.set_state(HashtagMgmtStates.selecting_category)
    await message.answer(
        f"✅ Категория <b>{name}</b> создана. Выберите категорию хештега:",
        reply_markup=category_select_keyboard(categories),
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Description + confirmation
# ---------------------------------------------------------------------------


@router.message(HashtagMgmtStates.entering_description, F.text)
async def msg_entering_description(
    message: Message, state: FSMContext, user: User | None = None
) -> None:
    """Save description and show confirmation."""
    if not _is_admin_or_owner(user):
        await state.clear()
        return

    description = (message.text or "").strip()
    logger.debug("[hashtag_mgmt] entering_description description=%r", description)

    await state.update_data(description=description)
    await state.set_state(HashtagMgmtStates.confirming)

    data = await state.get_data()
    tag = data.get("tag", "")
    category_id = data.get("category_id")

    category_label = "—"
    if category_id is not None:
        async with AsyncSessionLocal() as session:
            cat = await get_category_by_id(session, category_id)
        if cat is not None:
            category_label = _format_category_label(cat.name, cat.is_required)

    confirm_text = (
        "📋 <b>Информация о хештеге:</b>\n\n"
        f"Тег: <code>#{tag}</code>\n"
        f"Категория: {category_label}\n"
        f"Описание: {description}\n\n"
        "Выберите действие:"
    )
    logger.debug("[hashtag_mgmt] entering_description → confirming tag=%r", tag)
    await message.answer(
        confirm_text,
        reply_markup=hashtag_confirm_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "ht:save")
async def cb_ht_save(
    callback: CallbackQuery, state: FSMContext, user: User | None = None
) -> None:
    """Save (create or update) the hashtag."""
    if not _is_admin_or_owner(user):
        await callback.answer("Нет прав.", show_alert=True)
        return

    data = await state.get_data()
    tag = data.get("tag", "")
    description = data.get("description", "")
    category_id = data.get("category_id")
    hashtag_id = data.get("hashtag_id")
    telegram_id = callback.from_user.id if callback.from_user else 0

    logger.debug(
        "[hashtag_mgmt] ht:save tag=%r hashtag_id=%s telegram_id=%d",
        tag,
        hashtag_id,
        telegram_id,
    )

    async with AsyncSessionLocal() as session:
        if hashtag_id is not None:
            await update_hashtag(
                session,
                hashtag_id,
                tag=tag,
                description=description,
                category_id=category_id,
            )
        else:
            await create_hashtag(
                session,
                tag=tag,
                created_by=telegram_id,
                description=description,
                category_id=category_id,
            )
        await session.commit()

    await state.clear()
    logger.debug("[hashtag_mgmt] ht:save done tag=%r", tag)
    await callback.message.answer("✅ Хештег сохранён.")
    await callback.answer()


@router.callback_query(F.data == "ht:cancel")
async def cb_ht_cancel(
    callback: CallbackQuery, state: FSMContext, user: User | None = None
) -> None:
    """Cancel hashtag creation/edit; restore original data if editing."""
    if not _is_admin_or_owner(user):
        await callback.answer("Нет прав.", show_alert=True)
        return

    data = await state.get_data()
    hashtag_id = data.get("hashtag_id")
    original_data = data.get("original_data")

    logger.debug("[hashtag_mgmt] ht:cancel hashtag_id=%s", hashtag_id)

    if hashtag_id is not None and original_data is not None:
        async with AsyncSessionLocal() as session:
            await update_hashtag(session, hashtag_id, **original_data)
            await session.commit()
        logger.debug("[hashtag_mgmt] ht:cancel: restored original data for id=%d", hashtag_id)

    await state.clear()
    await callback.message.answer("❌ Отменено.")
    await callback.answer()


@router.callback_query(F.data == "ht:edit_field")
async def cb_ht_edit_field(
    callback: CallbackQuery, state: FSMContext, user: User | None = None
) -> None:
    """Return to tag entry to edit the current hashtag draft."""
    if not _is_admin_or_owner(user):
        await callback.answer("Нет прав.", show_alert=True)
        return

    data = await state.get_data()
    current_tag = data.get("tag", "")
    logger.debug("[hashtag_mgmt] ht:edit_field current_tag=%r → entering_tag", current_tag)

    await state.set_state(HashtagMgmtStates.entering_tag)
    await callback.message.answer(
        f"Введите новый хештег (или отправьте текущий <code>#{current_tag}</code>):",
        parse_mode="HTML",
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# View / Edit / Delete existing hashtag
# ---------------------------------------------------------------------------


@router.callback_query(F.data.startswith("ht:view:"))
async def cb_ht_view(
    callback: CallbackQuery, user: User | None = None
) -> None:
    """Show hashtag info with action keyboard."""
    if not _is_admin_or_owner(user):
        await callback.answer("Нет прав.", show_alert=True)
        return

    hashtag_id = int(callback.data.split(":")[2])
    logger.debug("[hashtag_mgmt] ht:view hashtag_id=%d", hashtag_id)

    async with AsyncSessionLocal() as session:
        hashtag = await get_hashtag_by_id(session, hashtag_id)
        if hashtag is None:
            await callback.answer("Хештег не найден.", show_alert=True)
            return
        tag = hashtag.tag
        description = hashtag.description or "—"
        category_label = "—"
        if hashtag.category_id is not None:
            cat = await get_category_by_id(session, hashtag.category_id)
            if cat is not None:
                category_label = _format_category_label(cat.name, cat.is_required)

    text = (
        f"🏷 <b>#{tag}</b>\n\n"
        f"Категория: {category_label}\n"
        f"Описание: {description}"
    )
    await callback.message.answer(
        text,
        reply_markup=hashtag_action_keyboard(hashtag_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ht:delete:"))
async def cb_ht_delete(
    callback: CallbackQuery, user: User | None = None
) -> None:
    """Delete hashtag by id and return to the list."""
    if not _is_admin_or_owner(user):
        await callback.answer("Нет прав.", show_alert=True)
        return

    hashtag_id = int(callback.data.split(":")[2])
    logger.debug("[hashtag_mgmt] delete hashtag_id=%d", hashtag_id)

    async with AsyncSessionLocal() as session:
        deleted = await delete_hashtag_by_id(session, hashtag_id)
        await session.commit()
        hashtags = await list_hashtags(session)

    if deleted:
        logger.debug("[hashtag_mgmt] delete: deleted hashtag_id=%d", hashtag_id)
        await callback.message.answer(
            "🗑 Хештег удалён.",
            reply_markup=hashtag_list_keyboard(hashtags),
        )
    else:
        await callback.message.answer("❌ Хештег не найден.")
    await callback.answer()


@router.callback_query(F.data.startswith("ht:edit:"))
async def cb_ht_edit(
    callback: CallbackQuery, state: FSMContext, user: User | None = None
) -> None:
    """Start editing an existing hashtag — prefill state with current values."""
    if not _is_admin_or_owner(user):
        await callback.answer("Нет прав.", show_alert=True)
        return

    hashtag_id = int(callback.data.split(":")[2])
    logger.debug("[hashtag_mgmt] edit hashtag_id=%d", hashtag_id)

    async with AsyncSessionLocal() as session:
        hashtag = await get_hashtag_by_id(session, hashtag_id)
        if hashtag is None:
            await callback.answer("Хештег не найден.", show_alert=True)
            return
        original_data = {
            "tag": hashtag.tag,
            "description": hashtag.description,
            "category_id": hashtag.category_id,
        }

    await state.set_state(HashtagMgmtStates.entering_tag)
    await state.update_data(
        hashtag_id=hashtag_id,
        original_data=original_data,
        tag=original_data["tag"],
        description=original_data["description"],
        category_id=original_data["category_id"],
    )
    logger.debug("[hashtag_mgmt] edit: entering_tag for hashtag_id=%d", hashtag_id)
    await callback.message.answer(
        f"Введите новый хештег (или отправьте текущий <code>#{original_data['tag']}</code>):",
        parse_mode="HTML",
    )
    await callback.answer()
