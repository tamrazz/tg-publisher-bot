import html
import logging
import re

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards import (
    announcement_actions_keyboard,
    duplicate_url_keyboard,
    moderation_keyboard,
)
from src.bot.states import ModerationStates
from src.db.models import User, UserRole
from src.db.repository import get_post
from src.db.session import AsyncSessionLocal
from src.publisher.channel import publish_to_channel
from src.services.pipeline import (
    process_url,
    publish_pending_post,
    regenerate_announcement,
    reject_post,
)

logger = logging.getLogger(__name__)
router = Router()

_URL_REGEX = re.compile(r"https?://\S+", re.IGNORECASE)


def _is_admin_or_owner(user: User | None) -> bool:
    return user is not None and user.role in (UserRole.owner, UserRole.admin)


@router.message(F.text.regexp(_URL_REGEX))
async def handle_url_message(message: Message, state: FSMContext, user: User | None = None) -> None:
    """Handle incoming URL messages from authorized users."""
    telegram_id = message.from_user.id if message.from_user else 0
    logger.debug("handle_url_message: from telegram_id=%d", telegram_id)

    if not _is_admin_or_owner(user):
        logger.warning("handle_url_message: unauthorized telegram_id=%d", telegram_id)
        return

    url = message.text.strip()
    logger.info("handle_url_message: processing url=%r telegram_id=%d", url, telegram_id)

    processing_msg = await message.answer("⏳ Обрабатываю ссылку...")

    try:
        bot: Bot = message.bot  # type: ignore[assignment]
        async with AsyncSessionLocal() as session:
            result = await process_url(
                url=url,
                created_by=telegram_id,
                session=session,
                bot=bot,
                moderate=True,  # always queue for admin approval first
            )
            await session.commit()

        if result.already_exists:
            logger.info(
                "handle_url_message: url already processed url=%r post_id=%d",
                url,
                result.post.id,
            )
            preview = (
                f"⚠️ <b>Ссылка уже была обработана</b> (пост #{result.post.id}).\n\n"
                f"{result.post_text}"
            )
            await processing_msg.edit_text(
                preview,
                parse_mode="HTML",
                reply_markup=duplicate_url_keyboard(result.post.id),
            )
            return

        logger.info("handle_url_message: pipeline done post_id=%d", result.post.id)
        preview = (
            f"📋 <b>Предварительный просмотр</b> (пост #{result.post.id}):\n\n{result.post_text}"
        )
        await processing_msg.edit_text(
            preview,
            parse_mode="HTML",
            reply_markup=announcement_actions_keyboard(result.post.id),
        )

    except Exception as exc:
        logger.error(
            "handle_url_message: pipeline failed url=%r: %s",
            url,
            exc,
            exc_info=True,
        )
        await processing_msg.edit_text(
            f"❌ Ошибка при обработке ссылки:\n<code>{html.escape(str(exc))}</code>",
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("publish_now:"))
async def handle_publish_now(
    query: CallbackQuery, state: FSMContext, user: User | None = None
) -> None:
    """Publish the post immediately without moderation."""
    telegram_id = query.from_user.id if query.from_user else 0
    logger.debug("handle_publish_now: telegram_id=%d data=%r", telegram_id, query.data)

    if not _is_admin_or_owner(user):
        await query.answer("Нет прав.")
        return

    post_id = int(query.data.split(":")[1])  # type: ignore[union-attr]
    logger.info("handle_publish_now: post_id=%d telegram_id=%d", post_id, telegram_id)

    await query.answer("Публикую...")
    bot: Bot = query.bot  # type: ignore[assignment]

    try:
        async with AsyncSessionLocal() as session:
            post = await publish_pending_post(post_id=post_id, session=session, bot=bot)
            await session.commit()

        if post is None:
            await query.message.edit_text(  # type: ignore[union-attr]
                "❌ Пост не найден или уже обработан."
            )
            return

        logger.info("handle_publish_now: published post_id=%d", post_id)
        await query.message.edit_text(f"✅ Пост #{post_id} опубликован.")  # type: ignore[union-attr]

    except Exception as exc:
        logger.error("handle_publish_now: error post_id=%d: %s", post_id, exc, exc_info=True)
        await query.message.edit_text(  # type: ignore[union-attr]
            f"❌ Ошибка публикации: <code>{exc}</code>", parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("moderate:"))
async def handle_send_to_moderation(
    query: CallbackQuery, state: FSMContext, user: User | None = None
) -> None:
    """Show full moderation keyboard."""
    telegram_id = query.from_user.id if query.from_user else 0
    logger.debug("handle_send_to_moderation: telegram_id=%d data=%r", telegram_id, query.data)

    if not _is_admin_or_owner(user):
        await query.answer("Нет прав.")
        return

    post_id = int(query.data.split(":")[1])  # type: ignore[union-attr]
    logger.info("handle_send_to_moderation: post_id=%d telegram_id=%d", post_id, telegram_id)

    await query.answer()
    await query.message.edit_reply_markup(  # type: ignore[union-attr]
        reply_markup=moderation_keyboard(post_id)
    )


@router.callback_query(F.data.startswith("approve:"))
async def handle_approve(query: CallbackQuery, state: FSMContext, user: User | None = None) -> None:
    """Approve and publish a post from moderation."""
    telegram_id = query.from_user.id if query.from_user else 0
    if not _is_admin_or_owner(user):
        await query.answer("Нет прав.")
        return

    post_id = int(query.data.split(":")[1])  # type: ignore[union-attr]
    logger.info("handle_approve: post_id=%d telegram_id=%d", post_id, telegram_id)

    await query.answer("Публикую...")
    bot: Bot = query.bot  # type: ignore[assignment]

    try:
        async with AsyncSessionLocal() as session:
            post = await publish_pending_post(post_id=post_id, session=session, bot=bot)
            await session.commit()

        if post is None:
            await query.message.edit_text(  # type: ignore[union-attr]
                "❌ Пост не найден или уже обработан."
            )
            return

        logger.info("handle_approve: published post_id=%d", post_id)
        await query.message.edit_text(f"✅ Пост #{post_id} опубликован.")  # type: ignore[union-attr]

    except Exception as exc:
        logger.error("handle_approve: error post_id=%d: %s", post_id, exc, exc_info=True)
        await query.message.edit_text(  # type: ignore[union-attr]
            f"❌ Ошибка: <code>{exc}</code>", parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("reject:"))
async def handle_reject(query: CallbackQuery, state: FSMContext, user: User | None = None) -> None:
    """Reject a pending post."""
    telegram_id = query.from_user.id if query.from_user else 0
    if not _is_admin_or_owner(user):
        await query.answer("Нет прав.")
        return

    post_id = int(query.data.split(":")[1])  # type: ignore[union-attr]
    logger.info("handle_reject: post_id=%d telegram_id=%d", post_id, telegram_id)

    await query.answer("Отклоняю...")

    async with AsyncSessionLocal() as session:
        post = await reject_post(post_id=post_id, session=session)
        await session.commit()

    if post is None:
        await query.message.edit_text("❌ Пост не найден.")  # type: ignore[union-attr]
        return

    logger.info("handle_reject: rejected post_id=%d", post_id)
    await query.message.edit_text(f"❌ Пост #{post_id} отклонён.")  # type: ignore[union-attr]


@router.callback_query(F.data.startswith("edit:"))
async def handle_edit_start(
    query: CallbackQuery, state: FSMContext, user: User | None = None
) -> None:
    """Enter editing mode for a post."""
    telegram_id = query.from_user.id if query.from_user else 0
    if not _is_admin_or_owner(user):
        await query.answer("Нет прав.")
        return

    post_id = int(query.data.split(":")[1])  # type: ignore[union-attr]
    logger.info("handle_edit_start: post_id=%d telegram_id=%d", post_id, telegram_id)

    await state.set_state(ModerationStates.editing_post)
    await state.update_data(editing_post_id=post_id)
    await query.answer()
    await query.message.answer(  # type: ignore[union-attr]
        f"✏️ Введите новый текст для поста #{post_id}:"
    )


@router.callback_query(F.data.startswith("dup_republish:"))
async def handle_dup_republish(
    query: CallbackQuery, state: FSMContext, user: User | None = None
) -> None:
    """Republish an existing post to the channel as-is."""
    telegram_id = query.from_user.id if query.from_user else 0
    if not _is_admin_or_owner(user):
        await query.answer("Нет прав.")
        return

    post_id = int(query.data.split(":")[1])  # type: ignore[union-attr]
    logger.info("[FIX] handle_dup_republish: post_id=%d telegram_id=%d", post_id, telegram_id)

    await query.answer("Публикую...")
    bot: Bot = query.bot  # type: ignore[assignment]

    try:
        async with AsyncSessionLocal() as session:
            post = await get_post(session, post_id)
            if post is None or not post.post_text:
                await query.message.edit_text(  # type: ignore[union-attr]
                    "❌ Пост не найден или текст пуста."
                )
                return
            await publish_to_channel(bot, post.post_text)
            await session.commit()

        logger.info("[FIX] handle_dup_republish: published post_id=%d", post_id)
        await query.message.edit_text(  # type: ignore[union-attr]
            f"✅ Пост #{post_id} опубликован повторно."
        )

    except Exception as exc:
        logger.error(
            "[FIX] handle_dup_republish: error post_id=%d: %s",
            post_id, exc, exc_info=True,
        )
        await query.message.edit_text(  # type: ignore[union-attr]
            f"❌ Ошибка публикации: <code>{html.escape(str(exc))}</code>", parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("dup_reprocess:"))
async def handle_dup_reprocess(
    query: CallbackQuery, state: FSMContext, user: User | None = None
) -> None:
    """Re-run the full pipeline for an already-processed URL, generating a fresh announcement."""
    telegram_id = query.from_user.id if query.from_user else 0
    if not _is_admin_or_owner(user):
        await query.answer("Нет прав.")
        return

    post_id = int(query.data.split(":")[1])  # type: ignore[union-attr]
    logger.info("[FIX] handle_dup_reprocess: post_id=%d telegram_id=%d", post_id, telegram_id)

    await query.answer("Генерирую заново...")
    bot: Bot = query.bot  # type: ignore[assignment]

    try:
        async with AsyncSessionLocal() as session:
            existing = await get_post(session, post_id)
            if existing is None:
                await query.message.edit_text("❌ Пост не найден.")  # type: ignore[union-attr]
                return
            url = existing.url

        await query.message.edit_text("⏳ Перегенерирую анонс...")  # type: ignore[union-attr]

        async with AsyncSessionLocal() as session:
            result = await process_url(
                url=url,
                created_by=telegram_id,
                session=session,
                bot=bot,
                moderate=True,
                force=True,
            )
            await session.commit()

        logger.info("[FIX] handle_dup_reprocess: new post_id=%d url=%r", result.post.id, url)
        preview = (
            f"📋 <b>Предварительный просмотр</b> (пост #{result.post.id}):\n\n{result.post_text}"
        )
        await query.message.edit_text(  # type: ignore[union-attr]
            preview,
            parse_mode="HTML",
            reply_markup=announcement_actions_keyboard(result.post.id),
        )

    except Exception as exc:
        logger.error(
            "[FIX] handle_dup_reprocess: error post_id=%d: %s",
            post_id, exc, exc_info=True,
        )
        await query.message.edit_text(  # type: ignore[union-attr]
            f"❌ Ошибка обработки: <code>{html.escape(str(exc))}</code>", parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("regenerate:"))
async def handle_regenerate(
    query: CallbackQuery, state: FSMContext, user: User | None = None
) -> None:
    """Re-generate the announcement using cached raw_content (no re-transcription)."""
    telegram_id = query.from_user.id if query.from_user else 0
    if not _is_admin_or_owner(user):
        await query.answer("Нет прав.")
        return

    post_id = int(query.data.split(":")[1])  # type: ignore[union-attr]
    logger.info("[FIX] handle_regenerate: post_id=%d telegram_id=%d", post_id, telegram_id)

    await query.answer("Перегенерирую...")
    await query.message.edit_text("⏳ Перегенерирую анонс...")  # type: ignore[union-attr]

    try:
        async with AsyncSessionLocal() as session:
            result = await regenerate_announcement(post_id=post_id, session=session)
            await session.commit()

        if result is None:
            await query.message.edit_text("❌ Пост не найден.")  # type: ignore[union-attr]
            return

        post, post_text = result
        logger.info("[FIX] handle_regenerate: done post_id=%d", post_id)
        preview = f"📋 <b>Предварительный просмотр</b> (пост #{post_id}):\n\n{post_text}"
        await query.message.edit_text(  # type: ignore[union-attr]
            preview,
            parse_mode="HTML",
            reply_markup=announcement_actions_keyboard(post_id),
        )

    except Exception as exc:
        logger.error("[FIX] handle_regenerate: error post_id=%d: %s", post_id, exc, exc_info=True)
        await query.message.edit_text(  # type: ignore[union-attr]
            f"❌ Ошибка перегенерации: <code>{html.escape(str(exc))}</code>", parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("edit_announce:"))
async def handle_edit_announce_start(
    query: CallbackQuery, state: FSMContext, user: User | None = None
) -> None:
    """Enter editing mode for an announcement (shows preview after editing, does not publish)."""
    telegram_id = query.from_user.id if query.from_user else 0
    if not _is_admin_or_owner(user):
        await query.answer("Нет прав.")
        return

    post_id = int(query.data.split(":")[1])  # type: ignore[union-attr]
    logger.info("[FIX] handle_edit_announce_start: post_id=%d telegram_id=%d", post_id, telegram_id)

    await state.set_state(ModerationStates.editing_announce)
    await state.update_data(editing_post_id=post_id)
    await query.answer()
    await query.message.answer(  # type: ignore[union-attr]
        f"✏️ Введите новый текст для поста #{post_id}:"
    )


@router.callback_query(F.data.startswith("dup_cancel:"))
async def handle_dup_cancel(
    query: CallbackQuery, state: FSMContext, user: User | None = None
) -> None:
    """Cancel — do nothing and dismiss the duplicate URL message."""
    telegram_id = query.from_user.id if query.from_user else 0
    post_id = int(query.data.split(":")[1])  # type: ignore[union-attr]
    logger.info("[FIX] handle_dup_cancel: post_id=%d telegram_id=%d", post_id, telegram_id)

    await query.answer("Отменено.")
    await query.message.edit_text(f"❌ Отменено (пост #{post_id}).")  # type: ignore[union-attr]
