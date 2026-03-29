import logging

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

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
