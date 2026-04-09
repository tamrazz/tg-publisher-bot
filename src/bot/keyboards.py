import logging
from typing import TYPE_CHECKING

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

if TYPE_CHECKING:
    from src.db.models import Hashtag, HashtagCategory

logger = logging.getLogger(__name__)


def initial_choice_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """
    Keyboard shown to the user right after pipeline runs:
    [Опубликовать сразу] [На модерацию]
    """
    logger.debug("initial_choice_keyboard: post_id=%d", post_id)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Опубликовать сразу",
                    callback_data=f"publish_now:{post_id}",
                ),
                InlineKeyboardButton(
                    text="👁 На модерацию",
                    callback_data=f"moderate:{post_id}",
                ),
            ]
        ]
    )


def duplicate_url_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """
    Keyboard shown when a URL was already processed:
    [🔁 Опубликовать ещё раз]
    [♻️ Сгенерировать заново]
    [❌ Отмена]
    """
    logger.debug("duplicate_url_keyboard: post_id=%d", post_id)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔁 Опубликовать ещё раз",
                    callback_data=f"dup_republish:{post_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="♻️ Сгенерировать заново",
                    callback_data=f"dup_reprocess:{post_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"dup_cancel:{post_id}",
                ),
            ],
        ]
    )


def announcement_actions_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """
    Keyboard shown after a new announcement is generated:
    [✅ Опубликовать] [♻️ Перегенерировать] [✏️ Изменить]
    """
    logger.debug("announcement_actions_keyboard: post_id=%d", post_id)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Опубликовать",
                    callback_data=f"publish_now:{post_id}",
                ),
                InlineKeyboardButton(
                    text="♻️ Перегенерировать",
                    callback_data=f"regenerate:{post_id}",
                ),
                InlineKeyboardButton(
                    text="✏️ Изменить",
                    callback_data=f"edit_announce:{post_id}",
                ),
            ]
        ]
    )


def settings_keyboard() -> InlineKeyboardMarkup:
    """
    Main /settings inline keyboard:
    [🏷 Хештеги]
    """
    logger.debug("settings_keyboard: building settings keyboard")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏷 Хештеги",
                    callback_data="settings:hashtags",
                ),
            ]
        ]
    )


def hashtag_list_keyboard(hashtags: list["Hashtag"]) -> InlineKeyboardMarkup:
    """
    Hashtag list keyboard:
    [➕ Добавить новый]
    [#tag] for each hashtag
    """
    logger.debug("hashtag_list_keyboard: count=%d", len(hashtags))
    rows = [
        [InlineKeyboardButton(text="➕ Добавить новый", callback_data="ht:new")]
    ]
    for h in hashtags:
        rows.append([InlineKeyboardButton(text=f"#{h.tag}", callback_data=f"ht:view:{h.id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def hashtag_action_keyboard(hashtag_id: int) -> InlineKeyboardMarkup:
    """
    Action keyboard for a specific hashtag:
    [✏️ Изменить] [🗑 Удалить]
    [⬅️ Назад]
    """
    logger.debug("hashtag_action_keyboard: hashtag_id=%d", hashtag_id)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Изменить", callback_data=f"ht:edit:{hashtag_id}"
                ),
                InlineKeyboardButton(
                    text="🗑 Удалить", callback_data=f"ht:delete:{hashtag_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад", callback_data="settings:hashtags"
                )
            ],
        ]
    )


def category_select_keyboard(
    categories: list["HashtagCategory"], selected_id: int | None = None
) -> InlineKeyboardMarkup:
    """
    Category selection keyboard:
    [➕ Добавить новую]
    [⚠️ name] for required categories, [name] for others
    """
    logger.debug(
        "category_select_keyboard: count=%d selected_id=%s", len(categories), selected_id
    )
    rows = [
        [InlineKeyboardButton(text="➕ Добавить новую", callback_data="cat:new")]
    ]
    for cat in categories:
        label = f"⚠️ {cat.name}" if cat.is_required else cat.name
        if cat.id == selected_id:
            label = f"✅ {label}"
        rows.append(
            [InlineKeyboardButton(text=label, callback_data=f"cat:pick:{cat.id}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def hashtag_confirm_keyboard() -> InlineKeyboardMarkup:
    """
    Confirmation keyboard:
    [✅ Сохранить] [✏️ Изменить] [❌ Отменить]
    """
    logger.debug("hashtag_confirm_keyboard: building confirm keyboard")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Сохранить", callback_data="ht:save"),
                InlineKeyboardButton(text="✏️ Изменить", callback_data="ht:edit_field"),
                InlineKeyboardButton(text="❌ Отменить", callback_data="ht:cancel"),
            ]
        ]
    )


def moderation_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """
    Moderation inline keyboard:
    [✅ Опубликовать] [✏️ Редактировать] [❌ Отклонить]
    """
    logger.debug("moderation_keyboard: post_id=%d", post_id)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Опубликовать",
                    callback_data=f"approve:{post_id}",
                ),
                InlineKeyboardButton(
                    text="✏️ Редактировать",
                    callback_data=f"edit:{post_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"reject:{post_id}",
                ),
            ]
        ]
    )
