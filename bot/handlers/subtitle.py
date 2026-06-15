"""Subtitle search command handler."""

import logging
import os
import re
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.models.subtitle_result import SubtitleResult
from bot.services.conversation_state_service import (
    ConversationStateService,
    PendingEpisodeRequest,
    PendingSyncRequest,
)
from bot.services.opensubtitles_service import (
    InvalidSubtitleQueryError,
    OpenSubtitlesAuthenticationError,
    OpenSubtitlesDownloadLinkExpiredError,
    OpenSubtitlesDowntimeError,
    OpenSubtitlesFileUnavailableError,
    OpenSubtitlesNoResultsError,
    OpenSubtitlesRateLimitError,
    OpenSubtitlesService,
    OpenSubtitlesServiceError,
)
from bot.services.groq_service import GroqService
from bot.services.subtitle_ranking_service import (
    SubtitleRankingService,
    detect_resolution,
    detect_source,
    format_download_count,
)
from bot.services.title_resolution_service import TitleResolutionService
from bot.services.tmdb_service import TmdbNoResultsError, TmdbService, TmdbServiceError
from config import ConfigError, get_settings

logger = logging.getLogger(__name__)

SEASON_EPISODE_PATTERN = re.compile(
    r"\b(?:s\d{1,2}\s*e\d{1,3}|season\s+\d{1,2}\s+episode\s+\d{1,3})\b",
    flags=re.IGNORECASE,
)
MAX_SUBTITLE_RESULTS = 10
DOWNLOAD_CALLBACK_PREFIX = "download_subtitle"
DOWNLOAD_COOLDOWN_SECONDS = 15.0
SYNC_STORAGE_ROOT = Path("tmp/sync")
SYNC_PROMPT = (
    "Is the subtitle timing okay?\n\n"
    "Reply with something like:\n\n"
    "* perfect\n"
    "* too fast\n"
    "* too slow\n"
    "* subtitles appear 2 seconds early\n"
    "* subtitles appear 3 seconds late"
)
_last_download_by_user: dict[int, float] = {}


async def subtitle_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resolve content through TMDb, then search OpenSubtitles metadata."""
    if update.message is None:
        return

    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("Usage: /subtitle <movie or TV show name>")
        return

    await run_subtitle_query(update.message, query)


async def run_subtitle_query(message: Message, query: str) -> None:
    """Resolve content through TMDb, then search OpenSubtitles metadata."""
    logger.info("Running subtitle search for query=%s", query)

    try:
        settings = get_settings()
        tmdb_service = TmdbService(settings.tmdb_api_key.get_secret_value())
        title_resolution = TitleResolutionService(
            tmdb_service=tmdb_service,
            groq_service=GroqService(settings.groq_api_key.get_secret_value()),
        ).resolve_user_query(query)

        if title_resolution.needs_episode:
            if message.from_user is not None:
                ConversationStateService().store_pending_episode_request(
                    message.from_user.id,
                    PendingEpisodeRequest(
                        tmdb_id=title_resolution.tmdb_id,
                        title=title_resolution.title,
                        original_query=query,
                        normalized_title=title_resolution.title,
                        year=title_resolution.year,
                        created_at=datetime.now(timezone.utc),
                    ),
                )
                logger.info(
                    "Stored pending episode request user_id=%s title=%s tmdb_id=%s",
                    message.from_user.id,
                    title_resolution.title,
                    title_resolution.tmdb_id,
                )

            await message.reply_text(
                "Which episode do you need?\n\n"
                f"Example:\n{title_resolution.title} S01E01"
            )
            return

        subtitles_service = OpenSubtitlesService(
            settings.opensubtitles_api_key.get_secret_value()
        )
        subtitle_query = title_resolution.normalized_query
        subtitles = select_subtitle_results(
            subtitles_service.search_subtitles(subtitle_query),
            subtitle_query,
        )
    except ConfigError:
        logger.exception("Subtitle command failed because configuration is invalid.")
        await message.reply_text(
            "Subtitle search is not configured yet. Please check TMDB_API_KEY "
            "and OPENSUBTITLES_API_KEY."
        )
        return
    except TmdbNoResultsError:
        await message.reply_text(
            "I couldn't find a match. Try including the full title, year, "
            "or episode format like: dark s01e03"
        )
        return
    except TmdbServiceError:
        logger.exception("TMDb identification failed during subtitle search.")
        await message.reply_text("Could not identify the title. Please try again later.")
        return
    except InvalidSubtitleQueryError:
        await message.reply_text("Please provide a valid subtitle search query.")
        return
    except OpenSubtitlesAuthenticationError:
        await message.reply_text("OpenSubtitles rejected the configured API key.")
        return
    except OpenSubtitlesNoResultsError:
        await message.reply_text("No subtitles found.")
        return
    except OpenSubtitlesDowntimeError:
        await message.reply_text("OpenSubtitles is unavailable. Please try again later.")
        return
    except OpenSubtitlesServiceError:
        logger.exception("OpenSubtitles search failed.")
        await message.reply_text("Subtitle search failed. Please try again later.")
        return

    await message.reply_text(
        "Choose a subtitle:",
        reply_markup=build_subtitle_keyboard(subtitles),
    )


async def subtitle_download_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Download a selected subtitle and send it to the user."""
    del context

    query = update.callback_query
    if query is None:
        return

    file_id = parse_download_callback_data(query.data or "")
    if file_id is None:
        await query.answer("Invalid subtitle selection.", show_alert=True)
        return

    user_id = query.from_user.id
    retry_after = get_download_retry_after(user_id)
    if retry_after > 0:
        await query.answer(
            f"Please wait {retry_after:.0f}s before downloading another subtitle.",
            show_alert=True,
        )
        return

    mark_download_attempt(user_id)

    try:
        settings = get_settings()
        subtitles_service = OpenSubtitlesService(
            settings.opensubtitles_api_key.get_secret_value()
        )
        download = subtitles_service.download_subtitle(file_id)
        temp_path = write_temp_subtitle_file(download.file_name, download.content)
    except ConfigError:
        logger.exception("Subtitle download failed because configuration is invalid.")
        await query.answer("Subtitle downloads are not configured.", show_alert=True)
        return
    except OpenSubtitlesAuthenticationError:
        await query.answer("OpenSubtitles rejected the configured API key.", show_alert=True)
        return
    except OpenSubtitlesDownloadLinkExpiredError:
        await query.answer("Download link expired. Run /subtitle again.", show_alert=True)
        return
    except OpenSubtitlesFileUnavailableError:
        await query.answer("Subtitle file is unavailable.", show_alert=True)
        return
    except OpenSubtitlesRateLimitError:
        await query.answer("OpenSubtitles rate limit reached. Try again later.", show_alert=True)
        return
    except OpenSubtitlesDowntimeError:
        await query.answer("OpenSubtitles is unavailable. Try again later.", show_alert=True)
        return
    except OpenSubtitlesServiceError:
        logger.exception("OpenSubtitles download failed.")
        await query.answer("Subtitle download failed. Try again later.", show_alert=True)
        return

    try:
        if query.message is None:
            return

        with open(temp_path, "rb") as subtitle_file:
            await query.message.reply_document(
                document=subtitle_file,
                filename=download.file_name,
                caption="Subtitle file",
            )
        retained_path = retain_subtitle_for_sync(
            query.from_user.id,
            temp_path,
            download.file_name,
        )
        if retained_path is not None:
            await query.message.reply_text(SYNC_PROMPT)
        await query.answer("Subtitle sent.")
    except TelegramError:
        logger.exception("Telegram failed to upload subtitle file.")
        await query.answer("Telegram upload failed. Please try again.", show_alert=True)
    finally:
        cleanup_temp_file(temp_path)


def build_tmdb_identification_query(query: str) -> str:
    """Build a TMDb-friendly query while preserving episode tokens for subtitles."""
    cleaned = SEASON_EPISODE_PATTERN.sub(" ", query)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or query.strip()


def format_subtitle_results(results: list[SubtitleResult]) -> str:
    """Format subtitle metadata for Telegram."""
    lines: list[str] = []

    for index, result in enumerate(results, start=1):
        release_name = result.release_name or result.file_name
        hearing_impaired = " [HI]" if result.hearing_impaired else ""
        lines.append(f"{index}. {result.language_label}{hearing_impaired}")
        lines.append(release_name)
        lines.append(f"Downloads: {result.download_count}")
        if index != len(results):
            lines.append("")

    return "\n".join(lines)


def build_subtitle_keyboard(results: list[SubtitleResult]) -> InlineKeyboardMarkup:
    """Build inline buttons for downloadable subtitle results."""
    buttons = [
        [
            InlineKeyboardButton(
                text=build_subtitle_button_label(result),
                callback_data=build_download_callback_data(result.file_id),
            )
        ]
        for result in results
    ]
    return InlineKeyboardMarkup(buttons)


def build_subtitle_button_label(result: SubtitleResult) -> str:
    """Build a compact subtitle button label."""
    release_text = result.release_name or result.file_name
    resolution = detect_resolution(release_text)
    source = detect_source(release_text)
    quality = " ".join(part for part in (resolution, source) if part != "Unknown")
    label = (
        f"{result.language_label} | {quality or 'Unknown'} | "
        f"{format_download_count(result.download_count)}"
    )
    return label[:64]


def select_subtitle_results(
    results: list[SubtitleResult],
    query: str,
) -> list[SubtitleResult]:
    """Rank subtitle results, then keep the top Telegram display options."""
    ranked_results = SubtitleRankingService().rank(results, query)
    return ranked_results[:MAX_SUBTITLE_RESULTS]


def build_download_callback_data(file_id: str) -> str:
    """Build callback data for a subtitle download selection."""
    return f"{DOWNLOAD_CALLBACK_PREFIX}:{file_id}"


def parse_download_callback_data(callback_data: str) -> str | None:
    """Extract the OpenSubtitles file id from callback data."""
    prefix = f"{DOWNLOAD_CALLBACK_PREFIX}:"
    if not callback_data.startswith(prefix):
        return None

    file_id = callback_data.removeprefix(prefix).strip()
    return file_id or None


def get_download_retry_after(user_id: int) -> float:
    """Return remaining local download cooldown in seconds."""
    last_download = _last_download_by_user.get(user_id)
    if last_download is None:
        return 0.0

    elapsed = time.monotonic() - last_download
    remaining = DOWNLOAD_COOLDOWN_SECONDS - elapsed
    return max(remaining, 0.0)


def mark_download_attempt(user_id: int) -> None:
    """Record a local download attempt for rate limiting."""
    _last_download_by_user[user_id] = time.monotonic()


def write_temp_subtitle_file(file_name: str, content: bytes) -> str:
    """Write subtitle bytes to a temporary file for Telegram upload."""
    suffix = os.path.splitext(file_name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(content)
        return temp_file.name


def cleanup_temp_file(path: str) -> None:
    """Remove a temporary subtitle file if it still exists."""
    try:
        os.unlink(path)
    except FileNotFoundError:
        return
    except OSError:
        logger.exception("Failed to clean up temporary subtitle file path=%s", path)


def retain_subtitle_for_sync(
    user_id: int,
    source_path: str,
    original_file_name: str,
) -> Path | None:
    """Keep a downloaded SRT file for a short sync-assistant session."""
    if Path(original_file_name).suffix.lower() != ".srt":
        logger.info("Skipping sync retention for unsupported subtitle file=%s", original_file_name)
        return None

    safe_name = build_safe_sync_file_name(original_file_name)
    user_dir = SYNC_STORAGE_ROOT / str(user_id)
    retained_path = user_dir / safe_name
    try:
        user_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, retained_path)
    except OSError:
        logger.exception("Failed to retain subtitle for sync user_id=%s", user_id)
        return None

    ConversationStateService().store_pending_sync_request(
        user_id,
        PendingSyncRequest(
            file_path=retained_path,
            original_file_name=original_file_name,
            created_at=datetime.now(timezone.utc),
        ),
    )
    logger.info(
        "Stored pending sync request user_id=%s file=%s",
        user_id,
        retained_path,
    )
    return retained_path


def build_safe_sync_file_name(file_name: str) -> str:
    """Build a safe local sync file name from a provider file name."""
    suffix = Path(file_name).suffix.lower() or ".srt"
    stem = Path(file_name).stem or "subtitle"
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-") or "subtitle"
    return f"{safe_stem}{suffix}"
