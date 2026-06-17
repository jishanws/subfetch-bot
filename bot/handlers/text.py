"""Natural-language text message handler."""

import logging
from pathlib import Path
import re

from telegram import Message
from telegram.error import TelegramError
from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.help import send_help_message
from bot.handlers.search import run_search_query
from bot.handlers.subtitle import run_subtitle_query
from bot.services.conversation_state_service import (
    ConversationStateService,
    PendingSyncRequest,
)
from bot.services.groq_service import GroqService
from bot.services.intent_service import Intent, IntentService
from bot.services.subtitle_sync_service import SubtitleSyncError, SubtitleSyncService
from bot.services.sync_intent_service import SyncIntent, SyncIntentService
from config import ConfigError, get_settings

logger = logging.getLogger(__name__)

SELECTION_MODE_MESSAGE = (
    "Selection mode is coming soon. For now, search subtitles directly, "
    "e.g. interstellar subtitle"
)
GREETING_MESSAGES = {"hi", "hello", "hey"}
ACKNOWLEDGEMENT_MESSAGES = {"thanks", "thank you", "thx", "ty"}
SYNC_AMOUNT_PROMPT = "How much?\nExamples:\n1s\n2s\n5s"


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route normal text messages through deterministic intent classification."""
    del context

    if update.message is None or update.message.text is None:
        return

    message = update.message.text.strip()
    logger.info("Received text message: %s", message)

    intent_service = IntentService()
    intent_result = intent_service.classify(message)

    normalized = intent_service._normalize(message)
    lowered = normalized.lower()

    has_episode = intent_service._contains_episode_pattern(normalized)
    cleaned_of_episode = intent_service.COMPACT_EPISODE_PATTERN.sub("", normalized)
    cleaned_of_episode = intent_service.SEASON_EPISODE_PATTERN.sub("", cleaned_of_episode).strip()
    has_title_with_episode = has_episode and bool(cleaned_of_episode)

    is_explicit_subtitle_search = bool(
        intent_service.SEARCH_PREFIX_PATTERN.match(normalized) or
        intent_service._contains_subtitle_term(lowered)
    )

    user_id = update.effective_user.id if update.effective_user else None

    # Priority A & B1: Explicit searches or TV episode queries with titles
    if is_explicit_subtitle_search or has_title_with_episode:
        if user_id:
            ConversationStateService().clear_pending_episode_request(user_id)
            ConversationStateService().clear_pending_sync_request(user_id)
        if intent_result.intent is Intent.SEARCH_TITLE and intent_result.query:
            await run_search_query(update.message, intent_result.query)
            return
        if intent_result.intent is Intent.FIND_SUBTITLE and intent_result.query:
            await run_subtitle_query(update.message, intent_result.query)
            return

    # Priority C: Pending episode request
    if await handle_pending_episode_reply(update, message):
        return

    # Priority B2: TV episode queries without titles ("s01e01")
    # Must never enter sync workflow
    if has_episode:
        if user_id:
            ConversationStateService().clear_pending_sync_request(user_id)
        if intent_result.intent is Intent.FIND_SUBTITLE and intent_result.query:
            await run_subtitle_query(update.message, intent_result.query)
            return

    # Priority D: Sync workflow
    if await handle_pending_sync_reply(update, message):
        return

    # Priority E: Greeting/help
    if intent_result.intent is Intent.HELP:
        await send_help_message(update.message)
        return

    if await handle_human_conversation_reply(update, message):
        return

    if message == "1":
        logger.info("Received unsupported selection-mode reply.")
        await update.message.reply_text(SELECTION_MODE_MESSAGE)
        return

    # Fallback for bare titles
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


async def handle_human_conversation_reply(update: Update, message: str) -> bool:
    """Handle simple conversational messages without triggering title search."""
    if update.message is None:
        return False

    normalized = normalize_conversation_message(message)
    if normalized in GREETING_MESSAGES:
        await update.message.reply_text(
            "Hi! Send a movie or TV show title to find subtitles."
        )
        return True
    if normalized in ACKNOWLEDGEMENT_MESSAGES:
        await update.message.reply_text("You’re welcome 🎬")
        return True
    return False


def normalize_conversation_message(message: str) -> str:
    """Normalize short conversational text for exact phrase matching."""
    lowered = message.lower()
    lowered = lowered.replace("'", "")
    lowered = lowered.replace("’", "")
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


async def handle_pending_sync_reply(update: Update, message: str) -> bool:
    """Handle a reply to the subtitle sync assistant."""
    if update.message is None or update.effective_user is None:
        return False

    state_service = ConversationStateService()
    user_id = update.effective_user.id
    pending_request = state_service.get_pending_sync_request(user_id)
    if pending_request is None:
        return False

    if state_service.is_pending_sync_expired(pending_request):
        logger.info("Pending sync request expired user_id=%s", user_id)
        state_service.clear_pending_sync_request(user_id)
        return False

    sync_result = build_sync_intent_service().classify(message)

    if sync_result.intent is SyncIntent.PERFECT:
        logger.info("Subtitle sync marked perfect user_id=%s", user_id)
        state_service.clear_pending_sync_request(user_id)
        await update.message.reply_text("Great. Enjoy the movie 🎬")
        return True

    if sync_result.intent is SyncIntent.NEED_AMOUNT:
        if pending_request.direction is None:
            await update.message.reply_text("Type the timing difference, for example:\n2s\n3.5 seconds\n5 sec")
            return True
        await apply_subtitle_sync(
            update.message,
            user_id,
            pending_request,
            pending_request.direction,
            sync_result.amount_seconds,
        )
        return True

    if sync_result.intent is SyncIntent.TOO_EARLY:
        if sync_result.amount_seconds is None:
            state_service.set_pending_sync_direction(user_id, "before_speech")
            from bot.handlers.subtitle import build_sync_amount_keyboard
            await update.message.reply_text("How far off is it?", reply_markup=build_sync_amount_keyboard())
            return True
        await apply_subtitle_sync(
            update.message,
            user_id,
            pending_request,
            "before_speech",
            sync_result.amount_seconds,
        )
        return True

    if sync_result.intent is SyncIntent.TOO_LATE:
        if sync_result.amount_seconds is None:
            state_service.set_pending_sync_direction(user_id, "after_speech")
            from bot.handlers.subtitle import build_sync_amount_keyboard
            await update.message.reply_text("How far off is it?", reply_markup=build_sync_amount_keyboard())
            return True
        await apply_subtitle_sync(
            update.message,
            user_id,
            pending_request,
            "after_speech",
            sync_result.amount_seconds,
        )
        return True

    await update.message.reply_text(
        "Reply with perfect, too fast, too slow, 2s early, or 3s late."
    )
    return True


async def apply_subtitle_sync(
    message: Message,
    user_id: int,
    pending_request: PendingSyncRequest,
    direction: str,
    amount_seconds: float | None,
) -> None:
    """Apply a sync shift and send the corrected subtitle file."""
    if amount_seconds is None:
        await message.reply_text("Type the timing difference, for example:\n2s\n3.5 seconds\n5 sec")
        return

    shift_seconds = amount_seconds if direction in ("early", "before_speech") else -amount_seconds
    corrected_path: Path | None = None

    try:
        corrected_path = SubtitleSyncService().shift_srt_file(
            pending_request.file_path,
            pending_request.original_file_name,
            shift_seconds,
        )
        from bot.handlers.subtitle import build_sync_fixed_keyboard
        with corrected_path.open("rb") as subtitle_file:
            await message.reply_document(
                document=subtitle_file,
                filename=corrected_path.name,
                caption="Did that fix it?",
                reply_markup=build_sync_fixed_keyboard()
            )
        
        import shutil
        shutil.copy2(corrected_path, pending_request.file_path)
        
    except (SubtitleSyncError, OSError, TelegramError):
        logger.exception("Subtitle sync failed user_id=%s", user_id)
        await message.reply_text("I could not sync that subtitle file. Download it again.")
        ConversationStateService().clear_pending_sync_request(user_id)
        return
    finally:
        if corrected_path is not None:
            try:
                corrected_path.unlink()
            except FileNotFoundError:
                pass
            try:
                corrected_path.parent.rmdir()
            except OSError:
                pass


def build_sync_intent_service() -> SyncIntentService:
    """Build sync intent classification with Groq as unknown-only fallback."""
    try:
        settings = get_settings()
    except ConfigError:
        return SyncIntentService()

    return SyncIntentService(
        GroqService(settings.groq_api_key.get_secret_value())
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
