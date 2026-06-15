"""Natural-language text message handler."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.help import send_help_message
from bot.handlers.search import run_search_query
from bot.handlers.subtitle import run_subtitle_query
from bot.services.conversation_state_service import ConversationStateService
from bot.services.intent_service import Intent, IntentService

logger = logging.getLogger(__name__)

SELECTION_MODE_MESSAGE = (
    "Selection mode is coming soon. For now, search subtitles directly, "
    "e.g. interstellar subtitle"
)


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route normal text messages through deterministic intent classification."""
    del context

    if update.message is None or update.message.text is None:
        return

    message = update.message.text.strip()
    logger.info("Received text message: %s", message)

    if await handle_pending_episode_reply(update, message):
        return

    if message == "1":
        logger.info("Received unsupported selection-mode reply.")
        await update.message.reply_text(SELECTION_MODE_MESSAGE)
        return

    intent_result = IntentService().classify(message)

    if intent_result.intent is Intent.HELP:
        await send_help_message(update.message)
        return

    if intent_result.intent is Intent.SEARCH_TITLE and intent_result.query:
        await run_search_query(update.message, intent_result.query)
        return

    if intent_result.intent is Intent.FIND_SUBTITLE and intent_result.query:
        await run_subtitle_query(update.message, intent_result.query)
        return

    logger.info("Could not classify natural-language message.")
    await update.message.reply_text(
        "I did not understand that yet. Try a title like interstellar subtitle, "
        "or send help."
    )


async def handle_pending_episode_reply(update: Update, message: str) -> bool:
    """Handle an episode-only reply for a pending TV show clarification."""
    if update.message is None or update.effective_user is None:
        return False

    state_service = ConversationStateService()
    user_id = update.effective_user.id
    pending_request = state_service.get_pending_episode_request(user_id)
    if pending_request is None:
        return False

    episode = state_service.parse_episode(message)
    if episode is None:
        logger.info(
            "Clearing pending episode request after different message user_id=%s title=%s",
            user_id,
            pending_request.title,
        )
        state_service.clear_pending_episode_request(user_id)
        return False

    season, episode_number = episode
    combined_query = state_service.build_episode_query(
        pending_request,
        season,
        episode_number,
    )
    logger.info(
        "Resolved pending episode request user_id=%s title=%s query=%s",
        user_id,
        pending_request.title,
        combined_query,
    )
    state_service.clear_pending_episode_request(user_id)
    await run_subtitle_query(update.message, combined_query)
    return True


text_message = handle_text_message
