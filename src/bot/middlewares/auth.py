import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from src.config import settings
from src.db.models import UserRole
from src.db.repository import get_or_create_user, get_user
from src.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    """
    OuterMiddleware that:
    1. Extracts the Telegram user from the incoming update.
    2. Gets or creates a DB User row (first owner gets owner role, others get admin).
    3. Silently drops updates from users not in OWNER_IDS and not already in DB.
    4. Injects ``user`` into handler data.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        update: Update = data.get("event_update") or event  # type: ignore[assignment]

        tg_user = None
        if isinstance(update, Update):
            if update.message and update.message.from_user:
                tg_user = update.message.from_user
            elif update.callback_query and update.callback_query.from_user:
                tg_user = update.callback_query.from_user

        if tg_user is None:
            logger.debug("AuthMiddleware: no user in update, passing through")
            return await handler(event, data)

        telegram_id = tg_user.id
        owner_ids = settings.owner_id_list

        logger.debug(
            "AuthMiddleware: update from telegram_id=%d username=%r",
            telegram_id,
            tg_user.username,
        )

        async with AsyncSessionLocal() as session:
            if telegram_id in owner_ids:
                # Auto-register owners on first contact
                db_user, created = await get_or_create_user(
                    session=session,
                    telegram_id=telegram_id,
                    username=tg_user.username,
                    role=UserRole.owner,
                )
                await session.commit()
                if created:
                    logger.info(
                        "AuthMiddleware: new owner registered telegram_id=%d",
                        telegram_id,
                    )
            else:
                # Non-owners must already exist in DB (manually granted admin access)
                db_user = await get_user(session, telegram_id)
                if db_user is None:
                    logger.warning(
                        "AuthMiddleware: unknown user telegram_id=%d, dropping update",
                        telegram_id,
                    )
                    return None
                if db_user.role not in (UserRole.owner, UserRole.admin):
                    logger.warning(
                        "AuthMiddleware: unauthorized user telegram_id=%d role=%s, dropping update",
                        telegram_id,
                        db_user.role,
                    )
                    return None

            logger.debug(
                "AuthMiddleware: authorized telegram_id=%d role=%s",
                telegram_id,
                db_user.role,
            )
            data["user"] = db_user

        return await handler(event, data)
