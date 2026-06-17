"""Search command handler."""

import logging

from telegram import Message, Update
from telegram.ext import ContextTypes

from bot.models.search_result import SearchResult
from bot.services.alias_service import AliasService
from bot.services.tmdb_service import (
    InvalidTmdbApiKeyError,
    TmdbNetworkError,
    TmdbNoResultsError,
    TmdbService,
    TmdbServiceError,
)
from config import ConfigError, get_settings

logger = logging.getLogger(__name__)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resolve a movie or TV show name using TMDb."""
    if update.message is None:
        return

    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("Usage: /search <movie or TV show name>")
        return

    await run_search_query(update.message, query)


async def run_search_query(message: Message, query: str) -> None:
    """Resolve a movie or TV show query using TMDb."""
    resolved_query = AliasService().resolve(query)
    logger.info("Running TMDb search for query=%s resolved_query=%s", query, resolved_query)

    try:
        settings = get_settings()
        service = TmdbService(settings.tmdb_api_key.get_secret_value())
        results = service.multi_search(resolved_query)[:5]
    except ConfigError:
        logger.exception("Search command failed because configuration is invalid.")
        await message.reply_text("Search is not configured yet. Please check TMDB_API_KEY.")
        return
    except InvalidTmdbApiKeyError:
        await message.reply_text("TMDb rejected the configured API key.")
        return
    except TmdbNoResultsError:
        await message.reply_text("No matching movies or TV shows found.")
        return
    except TmdbNetworkError:
        await message.reply_text("Could not reach TMDb. Please try again later.")
        return
    except TmdbServiceError:
        logger.exception("Search command failed due to a TMDb service error.")
        await message.reply_text("Search failed. Please try again later.")
        return

    await message.reply_text(format_search_results(results))


def format_search_results(results: list[SearchResult]) -> str:
    """Format top TMDb matches for a Telegram response."""
    lines: list[str] = []

    for index, result in enumerate(results, start=1):
        year = f" ({result.release_year})" if result.release_year else ""
        lines.append(f"{index}. {result.title}{year}")
        lines.append(result.media_type_label)
        if index != len(results):
            lines.append("")

    return "\n".join(lines)
