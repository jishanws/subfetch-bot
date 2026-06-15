"""Start command handler."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)
started_users: set[int] = set()

WELCOME_MESSAGE = (
    "Welcome to SubFetchBot 🎬\n\n"
    "Just type what you need:\n\n"
    "interstellar subtitle\n"
    "dark s01e03 subtitle\n"
    "the shawshank redemption\n\n"
    "For TV shows, include season and episode."
)
REPEATED_START_MESSAGE = (
    "Send a title to get started, for example:\n"
    "interstellar subtitle\n"
    "dark s01e03 subtitle"
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Initialize the bot for a user once per runtime."""
    del context

    if update.message is None:
        return

    if update.effective_user is None:
        logger.info("First /start received without a Telegram user id.")
        await update.message.reply_text(WELCOME_MESSAGE)
        return

    user_id = update.effective_user.id
    if user_id in started_users:
        logger.info("Repeated /start from user_id=%s.", user_id)
        await update.message.reply_text(REPEATED_START_MESSAGE)
        return

    logger.info("First /start from user_id=%s.", user_id)
    started_users.add(user_id)
    await update.message.reply_text(WELCOME_MESSAGE)
