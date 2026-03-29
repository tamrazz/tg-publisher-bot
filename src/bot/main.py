import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from src.config import settings
from src.db.session import engine

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.debug("Logging configured at level=%s", settings.log_level)


def create_bot() -> Bot:
    logger.debug("Creating Bot instance")
    return Bot(token=settings.bot_token)


def create_dispatcher() -> Dispatcher:
    logger.debug("Creating Dispatcher with MemoryStorage")
    dp = Dispatcher(storage=MemoryStorage())
    _register_routers(dp)
    _register_middlewares(dp)
    return dp


def _register_routers(dp: Dispatcher) -> None:
    from src.bot.handlers.edit_post import router as edit_router
    from src.bot.handlers.errors import router as errors_router
    from src.bot.handlers.hashtags import router as hashtags_router
    from src.bot.handlers.roles import router as roles_router
    from src.bot.handlers.url_input import router as url_router

    dp.include_router(roles_router)
    dp.include_router(hashtags_router)
    dp.include_router(edit_router)
    dp.include_router(url_router)
    dp.include_router(errors_router)
    logger.debug("Routers registered: roles, hashtags, edit_post, url_input, errors")


def _register_middlewares(dp: Dispatcher) -> None:
    from src.bot.middlewares.auth import AuthMiddleware

    dp.update.outer_middleware(AuthMiddleware())
    logger.debug("AuthMiddleware registered")


async def on_startup(bot: Bot) -> None:
    logger.info("Bot starting up — token prefix: %s...", settings.bot_token[:8])
    me = await bot.get_me()
    logger.info("Connected as @%s (id=%d)", me.username, me.id)


async def on_shutdown(bot: Bot) -> None:
    logger.info("Bot shutting down — closing DB engine")
    await engine.dispose()
    await bot.session.close()
    logger.info("Bot shutdown complete")


async def run_polling() -> None:
    setup_logging()
    bot = create_bot()
    dp = create_dispatcher()

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Starting long-polling")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
