import logging

from aiogram import Bot

from src.config import settings

logger = logging.getLogger(__name__)


async def publish_to_channel(bot: Bot, post_text: str) -> int:
    """
    Send *post_text* to the configured Telegram channel.
    Returns the message_id of the sent message.
    """
    channel_id = settings.telegram_channel_id
    logger.info(
        "publish_to_channel: channel_id=%s post_text_len=%d",
        channel_id,
        len(post_text),
    )

    message = await bot.send_message(
        chat_id=channel_id,
        text=post_text,
        parse_mode="HTML",
        disable_web_page_preview=False,
    )

    logger.info(
        "publish_to_channel: published message_id=%d channel_id=%s",
        message.message_id,
        channel_id,
    )
    return message.message_id
