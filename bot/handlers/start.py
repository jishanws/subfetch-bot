"""Start command handler."""

from telegram import Update
from telegram.ext import ContextTypes


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the /start command is received."""
    del context

    if update.message is None:
        return

    await update.message.reply_text(
        "Welcome to subfetch-bot.\n\n"
        "I will help you search, download, and synchronize subtitles for "
        "movies and TV shows. Subtitle search is coming in a later release.\n\n"
        "Use /help to see available commands."
    )

