"""Telegram bot entry point."""

import logging

from telegram.ext import Application, ApplicationBuilder, CallbackQueryHandler, CommandHandler

from bot.handlers.help import help_command
from bot.handlers.search import search_command
from bot.handlers.start import start_command
from bot.handlers.subtitle import DOWNLOAD_CALLBACK_PREFIX, subtitle_command, subtitle_download_callback
from config import get_settings

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def create_application(token: str) -> Application:
    """Create and configure the Telegram application."""
    application = ApplicationBuilder().token(token).build()
    register_handlers(application)
    return application


def register_handlers(application: Application) -> None:
    """Register Telegram command handlers."""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("subtitle", subtitle_command))
    application.add_handler(
        CallbackQueryHandler(
            subtitle_download_callback,
            pattern=f"^{DOWNLOAD_CALLBACK_PREFIX}:",
        )
    )


def main() -> None:
    """Run the bot in polling mode."""
    settings = get_settings()
    token = settings.telegram_bot_token.get_secret_value()
    application = create_application(token)

    logger.info("Starting subfetch-bot in polling mode.")
    application.run_polling()


if __name__ == "__main__":
    main()
