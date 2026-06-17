"""Tests for subtitle response formatting."""

from datetime import datetime, timezone
from types import SimpleNamespace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from bot.handlers.subtitle import (
    build_download_callback_data,
    build_episode_keyboard,
    build_sync_keyboard,
    build_subtitle_keyboard,
    build_tmdb_identification_query,
    cleanup_temp_file,
    format_subtitle_results,
    get_download_retry_after,
    mark_download_attempt,
    parse_download_callback_data,
    retain_subtitle_for_sync,
    select_subtitle_results,
    subtitle_download_callback,
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

        self.assertEqual(button.text, "BluRay\nEnglish | BluRay | 12k | OS")
        self.assertEqual(button.callback_data, "download_subtitle:101")

    def test_build_subtitle_button_label_formatting(self) -> None:
        from bot.handlers.subtitle import build_subtitle_button_label

        # Preferred format: Release name \n English | 1080p BluRay | 39.0k
        result = SubtitleResult(
            subtitle_id="1",
            file_id="101",
            language="en",
            file_name="GOT.S05E07.1080p.BDRip.srt",
            download_count=39000,
            hearing_impaired=False,
            release_name="Game.Of.Thrones.S05E07.The.Gift.1080p.BDRip",
        )
        label = build_subtitle_button_label(result)
        self.assertEqual(
            label,
            "Game.Of.Thrones.S05E07...BDRip\nEnglish | 1080p BluRay | 39k | OS",
        )

        # Fallback to file name, removes extension
        result2 = SubtitleResult(
            subtitle_id="2",
            file_id="102",
            language="en",
            file_name="Dark.S01E03.1080p.WEB-DL.srt",
            download_count=1200,
            hearing_impaired=False,
            release_name="",
        )
        label2 = build_subtitle_button_label(result2)
        self.assertEqual(
            label2,
            "Dark.S01E03.1080p.WEB-DL\nEnglish | 1080p WEB-DL | 1.2k | OS",
        )

        # Truncates middle safely if very long
        result3 = SubtitleResult(
            subtitle_id="3",
            file_id="103",
            language="en",
            file_name="Some.Very.Long.Release.Name.That.Exceeds.Telegram.Button.Length.Limits.1080p.WEB-DL.srt",
            download_count=100,
            hearing_impaired=False,
            release_name="",
        )
        label3 = build_subtitle_button_label(result3)
        self.assertLessEqual(len(label3), 64)
        self.assertTrue(label3.startswith("Some.Very.Long.R"))
        self.assertTrue("...EB-DL\nEnglish" in label3)

        # Fallback for completely missing release
        result4 = SubtitleResult(
            subtitle_id="4",
            file_id="104",
            language="en",
            file_name=" ",
            download_count=10,
            hearing_impaired=False,
            release_name="",
        )
        label4 = build_subtitle_button_label(result4)
        self.assertEqual(
            label4,
            "Unknown release\nEnglish | Unknown | 10 | OS",
        )

    def test_build_episode_keyboard(self) -> None:
        keyboard = build_episode_keyboard()
        buttons = keyboard.inline_keyboard[0]

        self.assertEqual(buttons[0].text, "Enter Episode")
        self.assertEqual(buttons[0].callback_data, "episode:enter")
        self.assertEqual(buttons[1].text, "Cancel")
        self.assertEqual(buttons[1].callback_data, "episode:cancel")

    def test_build_sync_keyboard(self) -> None:
        keyboard = build_sync_keyboard()
        buttons = keyboard.inline_keyboard

        self.assertEqual(buttons[0][0].text, "✅ Looks good")
        self.assertEqual(buttons[0][0].callback_data, "sync:perfect")
        self.assertEqual(buttons[1][0].text, "💬 Text appears before people speak")
        self.assertEqual(buttons[1][0].callback_data, "sync:before_speech")
        self.assertEqual(buttons[2][0].text, "💬 Text appears after people speak")
        self.assertEqual(buttons[2][0].callback_data, "sync:after_speech")

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
        pending_sync_requests.clear()

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
        self.assertEqual(pending_episode_requests[1001].user_id, 1001)
        self.assertEqual(pending_episode_requests[1001].media_type, "tv")
        message.reply_text.assert_awaited_once()
        self.assertEqual(
            message.reply_text.await_args.args[0],
            "Which episode do you need?\n\nExample: Game of Thrones S01E01",
        )
        self.assertIsNotNone(message.reply_text.await_args.kwargs["reply_markup"])

    async def test_episode_cancel_button_clears_pending_state(self) -> None:
        pending_episode_requests[1001] = SimpleNamespace()
        update = build_callback_update(1001, "episode:cancel")

        await subtitle_download_callback(update, None)

        self.assertNotIn(1001, pending_episode_requests)
        update.callback_query.answer.assert_awaited_once_with("Cancelled.")
        update.callback_query.message.reply_text.assert_awaited_once_with(
            "Cancelled. Send a title when you're ready."
        )

    async def test_sync_before_speech_button_asks_for_amount(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "subtitle.srt"
            file_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n", encoding="utf-8")
            pending_sync_requests[1001] = SimpleNamespace(
                file_path=file_path,
                original_file_name="subtitle.srt",
                created_at=datetime.now(timezone.utc),
                direction=None,
            )
            update = build_callback_update(1001, "sync:before_speech")

            from bot.handlers.subtitle import handle_sync_callback
            await handle_sync_callback(update, "sync:before_speech")

        update.callback_query.answer.assert_awaited_once_with()
        update.callback_query.message.reply_text.assert_awaited_once()
        self.assertEqual(
            update.callback_query.message.reply_text.await_args.args[0],
            "How far off is it?",
        )
        self.assertEqual(pending_sync_requests[1001].direction, "before_speech")


def fake_settings() -> SimpleNamespace:
    """Build settings with fake secret values for subtitle handler tests."""
    secret = SimpleNamespace(get_secret_value=lambda: "fake")
    return SimpleNamespace(
        tmdb_api_key=secret,
        groq_api_key=secret,
        opensubtitles_api_key=secret,
    )


def build_callback_update(user_id: int, data: str) -> SimpleNamespace:
    """Build a minimal Telegram callback update stand-in."""
    return SimpleNamespace(
        callback_query=SimpleNamespace(
            data=data,
            from_user=SimpleNamespace(id=user_id),
            message=SimpleNamespace(reply_text=AsyncMock()),
            answer=AsyncMock(),
        )
    )


if __name__ == "__main__":
    unittest.main()
