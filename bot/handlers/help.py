"""Help command handler."""

from telegram import Update
from telegram.ext import ContextTypes


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the list of currently available commands."""
    del context

    if update.message is None:
        return

    await update.message.reply_text(
        "Available commands:\n\n"
        "/start - Start the bot and view the welcome message\n"
        "/help - Show this help message\n\n"
        "Subtitle search and synchronization commands will be added later."
    )

