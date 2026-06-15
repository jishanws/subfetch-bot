"""Tests for subtitle response formatting."""

from types import SimpleNamespace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from bot.handlers.subtitle import (
    build_download_callback_data,
    build_subtitle_keyboard,
    build_tmdb_identification_query,
    cleanup_temp_file,
    format_subtitle_results,
    get_download_retry_after,
    mark_download_attempt,
    parse_download_callback_data,
    retain_subtitle_for_sync,
    select_subtitle_results,
    write_temp_subtitle_file,
    _last_download_by_user,
    run_subtitle_query,
)
from bot.models.subtitle_result import SubtitleResult
from bot.services.conversation_state_service import (
    pending_sync_requests,
    pending_episode_requests,
)
from bot.services.title_resolution_service import TitleResolution


class SubtitleHandlerTests(unittest.TestCase):
    """Subtitle handler unit tests."""

    def test_format_subtitle_results(self) -> None:
        results = [
            SubtitleResult(
                subtitle_id="1",
                file_id="101",
                language="en",
                file_name="file-1.srt",
                download_count=12000,
                hearing_impaired=False,
                release_name="BluRay",
            ),
            SubtitleResult(
                subtitle_id="2",
                file_id="102",
                language="bn",
                file_name="file-2.srt",
                download_count=2000,
                hearing_impaired=False,
                release_name="WEBRip",
            ),
        ]

        self.assertEqual(
            format_subtitle_results(results),
            "1. English\n"
            "BluRay\n"
            "Downloads: 12000\n\n"
            "2. Bengali\n"
            "WEBRip\n"
            "Downloads: 2000",
        )

    def test_build_tmdb_identification_query_removes_episode_token(self) -> None:
        self.assertEqual(
            build_tmdb_identification_query("breaking bad s02e05"),
            "breaking bad",
        )

    def test_build_subtitle_keyboard_uses_file_id_callback_data(self) -> None:
        result = SubtitleResult(
            subtitle_id="1",
            file_id="101",
            language="en",
            file_name="file-1.srt",
            download_count=12000,
            hearing_impaired=False,
            release_name="BluRay",
        )

        keyboard = build_subtitle_keyboard([result])
        button = keyboard.inline_keyboard[0][0]

        self.assertEqual(button.text, "English | BluRay | 12k downloads")
        self.assertEqual(button.callback_data, "download_subtitle:101")

    def test_select_subtitle_results_respects_top_10_limit_after_ranking(self) -> None:
        results = [
            SubtitleResult(
                subtitle_id=str(index),
                file_id=str(index),
                language="en",
                file_name=f"dark-s01e03-1080p-web-dl-{index}.srt",
                download_count=index,
                hearing_impaired=False,
                release_name=f"Dark.S01E03.1080p.WEB-DL.{index}",
            )
            for index in range(11)
        ]

        selected = select_subtitle_results(results, "dark s01e03")

        self.assertEqual(len(selected), 10)
        self.assertEqual(selected[0].file_id, "10")

    def test_download_callback_data_round_trip(self) -> None:
        callback_data = build_download_callback_data("101")

        self.assertEqual(parse_download_callback_data(callback_data), "101")
        self.assertIsNone(parse_download_callback_data("invalid:101"))

    def test_download_rate_limit_tracks_user_cooldown(self) -> None:
        _last_download_by_user.clear()

        self.assertEqual(get_download_retry_after(123), 0.0)
        mark_download_attempt(123)

        self.assertGreater(get_download_retry_after(123), 0.0)

    def test_temp_subtitle_file_cleanup(self) -> None:
        path = write_temp_subtitle_file("subtitle.srt", b"content")

        with open(path, "rb") as subtitle_file:
            self.assertEqual(subtitle_file.read(), b"content")

        cleanup_temp_file(path)

        with self.assertRaises(FileNotFoundError):
            open(path, "rb")

    def test_downloaded_subtitle_stores_pending_sync_state(self) -> None:
        pending_sync_requests.clear()

        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "subtitle.srt"
            source_path.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\nHi\n",
                encoding="utf-8",
            )

            retained_path = retain_subtitle_for_sync(
                1001,
                str(source_path),
                "Movie Subtitle.srt",
            )

        self.assertIsNotNone(retained_path)
        self.assertIn(1001, pending_sync_requests)
        self.assertEqual(pending_sync_requests[1001].original_file_name, "Movie Subtitle.srt")
        self.assertTrue(pending_sync_requests[1001].file_path.exists())
        pending_sync_requests[1001].file_path.unlink()
        pending_sync_requests.clear()


class SubtitleHandlerAsyncTests(unittest.IsolatedAsyncioTestCase):
    """Subtitle handler async flow tests."""

    def setUp(self) -> None:
        pending_episode_requests.clear()

    async def test_tv_show_without_episode_stores_pending_state(self) -> None:
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=1001),
            reply_text=AsyncMock(),
        )
        resolution = TitleResolution(
            normalized_query="Game of Thrones",
            media_type="tv",
            tmdb_id=1399,
            title="Game of Thrones",
            year=2011,
            needs_episode=True,
            season=None,
            episode=None,
        )

        with (
            patch("bot.handlers.subtitle.get_settings", return_value=fake_settings()),
            patch("bot.handlers.subtitle.TmdbService"),
            patch("bot.handlers.subtitle.GroqService"),
            patch("bot.handlers.subtitle.TitleResolutionService") as service_class,
        ):
            service_class.return_value.resolve_user_query.return_value = resolution
            await run_subtitle_query(message, "GOT")

        self.assertIn(1001, pending_episode_requests)
        self.assertEqual(pending_episode_requests[1001].title, "Game of Thrones")
        message.reply_text.assert_awaited_once_with(
            "Which episode do you need?\n\n"
            "Example:\nGame of Thrones S01E01"
        )


def fake_settings() -> SimpleNamespace:
    """Build settings with fake secret values for subtitle handler tests."""
    secret = SimpleNamespace(get_secret_value=lambda: "fake")
    return SimpleNamespace(
        tmdb_api_key=secret,
        groq_api_key=secret,
        opensubtitles_api_key=secret,
    )


if __name__ == "__main__":
    unittest.main()
