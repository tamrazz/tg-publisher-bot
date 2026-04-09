"""
Legacy hashtag command handlers — replaced by the settings FSM flow.

The commands /add_hashtag, /list_hashtags, /delete_hashtag have been removed.
Use /settings → Хештеги instead.
"""
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("add_hashtag"))
async def handle_add_hashtag_legacy(message: Message) -> None:
    logger.debug("handle_add_hashtag_legacy: deprecated command used")
    await message.answer(
        "Эта команда устарела. Используйте /settings → 🏷 Хештеги для управления хештегами."
    )


@router.message(Command("list_hashtags"))
async def handle_list_hashtags_legacy(message: Message) -> None:
    logger.debug("handle_list_hashtags_legacy: deprecated command used")
    await message.answer(
        "Эта команда устарела. Используйте /settings → 🏷 Хештеги для управления хештегами."
    )


@router.message(Command("delete_hashtag"))
async def handle_delete_hashtag_legacy(message: Message) -> None:
    logger.debug("handle_delete_hashtag_legacy: deprecated command used")
    await message.answer(
        "Эта команда устарела. Используйте /settings → 🏷 Хештеги для управления хештегами."
    )
