"""Telegram handler registration."""

import logging
from typing import Callable

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.handlers.help import help_command
from bot.handlers.search import search_command
from bot.handlers.start import start_command
from bot.handlers.subtitle import (
    DOWNLOAD_CALLBACK_PREFIX,
    EPISODE_CALLBACK_PREFIX,
    SYNC_CALLBACK_PREFIX,
    subtitle_command,
    subtitle_download_callback,
)
from bot.handlers.text import handle_text_message

logger = logging.getLogger(__name__)


def register_handlers(application: Application) -> None:
    """Register all Telegram handlers in one place."""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("subtitle", subtitle_command))
    application.add_handler(
        CallbackQueryHandler(
            subtitle_download_callback,
            pattern=f"^(?:{DOWNLOAD_CALLBACK_PREFIX}|{EPISODE_CALLBACK_PREFIX}|{SYNC_CALLBACK_PREFIX}):",
        )
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)
    )
    log_registered_handlers(application)


def log_registered_handlers(application: Application) -> None:
    """Log all registered Telegram handlers with group and callback names."""
    for group, handlers in application.handlers.items():
        for handler in handlers:
            callback = getattr(handler, "callback", None)
            callback_name = get_callback_name(callback)
            logger.info(
                "Registered handler group=%s type=%s callback=%s",
                group,
                type(handler).__name__,
                callback_name,
            )


def get_callback_name(callback: Callable[..., object] | None) -> str:
    """Return a readable callback name for handler registration logs."""
    if callback is None:
        return "<none>"
    return getattr(callback, "__name__", repr(callback))
