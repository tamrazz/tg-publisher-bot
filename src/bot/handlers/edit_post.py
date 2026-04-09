import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot.keyboards import announcement_actions_keyboard
from src.bot.states import ModerationStates
from src.db.models import User, UserRole
from src.db.repository import update_post_text
from src.db.session import AsyncSessionLocal
from src.services.pipeline import publish_pending_post

logger = logging.getLogger(__name__)
router = Router()


def _is_admin_or_owner(user: User | None) -> bool:
    return user is not None and user.role in (UserRole.owner, UserRole.admin)


@router.message(ModerationStates.editing_post, F.text)
async def handle_edited_post_text(
    message: Message, state: FSMContext, user: User | None = None
) -> None:
    """
    Receive edited post text and publish the post with the new content.
    """
    telegram_id = message.from_user.id if message.from_user else 0
    logger.debug("handle_edited_post_text: telegram_id=%d", telegram_id)

    if not _is_admin_or_owner(user):
        await state.clear()
        return

    data = await state.get_data()
    post_id: int | None = data.get("editing_post_id")

    if post_id is None:
        logger.warning("handle_edited_post_text: no post_id in state telegram_id=%d", telegram_id)
        await state.clear()
        await message.answer("❌ Ошибка: не найден редактируемый пост. Попробуйте снова.")
        return

    new_text = message.text or ""
    logger.info(
        "handle_edited_post_text: post_id=%d new_text_len=%d telegram_id=%d",
        post_id,
        len(new_text),
        telegram_id,
    )

    await state.clear()
    bot: Bot = message.bot  # type: ignore[assignment]

    try:
        async with AsyncSessionLocal() as session:
            post = await publish_pending_post(
                post_id=post_id,
                edited_text=new_text,
                session=session,
                bot=bot,
            )
            await session.commit()

        if post is None:
            await message.answer("❌ Пост не найден или уже обработан.")
            return

        logger.info("handle_edited_post_text: published post_id=%d with edited text", post_id)
        await message.answer(f"✅ Пост #{post_id} отредактирован и опубликован.")

    except Exception as exc:
        logger.error("handle_edited_post_text: error post_id=%d: %s", post_id, exc, exc_info=True)
        await message.answer(f"❌ Ошибка публикации: <code>{exc}</code>", parse_mode="HTML")


@router.message(ModerationStates.editing_announce, F.text)
async def handle_edited_announce_text(
    message: Message, state: FSMContext, user: User | None = None
) -> None:
    """
    Receive edited post text for the announce flow.
    Updates the post text in DB and shows the preview again — does NOT publish.
    """
    telegram_id = message.from_user.id if message.from_user else 0
    logger.debug("[FIX] handle_edited_announce_text: telegram_id=%d", telegram_id)

    if not _is_admin_or_owner(user):
        await state.clear()
        return

    data = await state.get_data()
    post_id: int | None = data.get("editing_post_id")

    if post_id is None:
        logger.warning(
            "[FIX] handle_edited_announce_text: no post_id in state telegram_id=%d", telegram_id
        )
        await state.clear()
        await message.answer("❌ Ошибка: не найден редактируемый пост. Попробуйте снова.")
        return

    new_text = message.text or ""
    logger.info(
        "[FIX] handle_edited_announce_text: post_id=%d new_text_len=%d telegram_id=%d",
        post_id,
        len(new_text),
        telegram_id,
    )

    await state.clear()

    try:
        async with AsyncSessionLocal() as session:
            post = await update_post_text(session, post_id, new_text)
            await session.commit()

        if post is None:
            await message.answer("❌ Пост не найден.")
            return

        logger.info("[FIX] handle_edited_announce_text: updated post_id=%d", post_id)
        preview = f"📋 <b>Предварительный просмотр</b> (пост #{post_id}):\n\n{new_text}"
        await message.answer(
            preview,
            parse_mode="HTML",
            reply_markup=announcement_actions_keyboard(post_id),
        )

    except Exception as exc:
        logger.error(
            "[FIX] handle_edited_announce_text: error post_id=%d: %s", post_id, exc, exc_info=True
        )
        await message.answer(f"❌ Ошибка сохранения: <code>{exc}</code>", parse_mode="HTML")
