import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User, UserRole
from src.db.repository import delete_user, get_user, update_user_role

logger = logging.getLogger(__name__)


async def add_admin(session: AsyncSession, target_telegram_id: int) -> User | None:
    """
    Promote a user to admin role.
    Returns the updated User, or None if user not found.
    """
    logger.info("add_admin: promoting telegram_id=%d to admin", target_telegram_id)
    user = await get_user(session, target_telegram_id)
    if user is None:
        logger.warning("add_admin: user not found telegram_id=%d", target_telegram_id)
        return None

    if user.role == UserRole.owner:
        logger.warning("add_admin: cannot demote owner telegram_id=%d", target_telegram_id)
        return None

    updated = await update_user_role(session, target_telegram_id, UserRole.admin)
    logger.info("add_admin: telegram_id=%d → role=admin", target_telegram_id)
    return updated


async def remove_admin(session: AsyncSession, target_telegram_id: int) -> bool:
    """
    Remove a user from the admin list (delete their DB record).
    Returns True if deleted, False if not found.
    Owners cannot be removed this way.
    """
    logger.info("remove_admin: removing telegram_id=%d", target_telegram_id)
    user = await get_user(session, target_telegram_id)
    if user is None:
        logger.warning("remove_admin: user not found telegram_id=%d", target_telegram_id)
        return False

    if user.role == UserRole.owner:
        logger.warning("remove_admin: cannot remove owner telegram_id=%d", target_telegram_id)
        return False

    deleted = await delete_user(session, target_telegram_id)
    if deleted:
        logger.info("remove_admin: deleted telegram_id=%d", target_telegram_id)
    return deleted
