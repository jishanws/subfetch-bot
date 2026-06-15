"""Help command handler."""

from telegram import Message, Update
from telegram.ext import ContextTypes


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the list of currently available commands."""
    del context

    if update.message is None:
        return

    await send_help_message(update.message)


async def send_help_message(message: Message) -> None:
    """Send the list of currently available commands."""
    await message.reply_text(
        "Available commands:\n\n"
        "/start - Start the bot and view the welcome message\n"
        "/help - Show this help message\n"
        "/search <query> - Search movies and TV shows\n"
        "/subtitle <query> - Find subtitles\n\n"
        "You can also type naturally, e.g. interstellar subtitle, "
        "dark s01e03 english subtitle, or search breaking bad."
    )
