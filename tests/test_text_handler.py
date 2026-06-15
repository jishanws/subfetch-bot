"""Tests for natural-language text handler state handling."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot.handlers.text import handle_pending_episode_reply, handle_text_message
from bot.services.conversation_state_service import (
    ConversationStateService,
    PendingEpisodeRequest,
    PendingSyncRequest,
    pending_episode_requests,
    pending_sync_requests,
)


class TextHandlerPendingEpisodeTests(unittest.IsolatedAsyncioTestCase):
    """Pending TV episode reply tests."""

    def setUp(self) -> None:
        pending_episode_requests.clear()
        pending_sync_requests.clear()
        self.state_service = ConversationStateService()

    async def test_user_reply_combines_with_pending_show(self) -> None:
        self.state_service.store_pending_episode_request(1001, self.pending_request())
        update = build_update(user_id=1001)

        with patch("bot.handlers.text.run_subtitle_query", new=AsyncMock()) as run_query:
            handled = await handle_pending_episode_reply(update, "s05 e5")

        self.assertTrue(handled)
        run_query.assert_awaited_once_with(update.message, "Game of Thrones S05E05")

    async def test_pending_state_clears_after_successful_episode_reply(self) -> None:
        self.state_service.store_pending_episode_request(1001, self.pending_request())
        update = build_update(user_id=1001)

        with patch("bot.handlers.text.run_subtitle_query", new=AsyncMock()):
            await handle_pending_episode_reply(update, "s05 e5")

        self.assertIsNone(self.state_service.get_pending_episode_request(1001))

    async def test_different_new_title_clears_pending_state(self) -> None:
        self.state_service.store_pending_episode_request(1001, self.pending_request())
        update = build_update(user_id=1001)

        handled = await handle_pending_episode_reply(update, "interstellar subtitle")

        self.assertFalse(handled)
        self.assertIsNone(self.state_service.get_pending_episode_request(1001))

    async def test_different_new_title_continues_normal_processing(self) -> None:
        self.state_service.store_pending_episode_request(1001, self.pending_request())
        update = build_update(user_id=1001, text="interstellar subtitle")

        with patch("bot.handlers.text.run_subtitle_query", new=AsyncMock()) as run_query:
            await handle_text_message(update, None)

        run_query.assert_awaited_once_with(update.message, "interstellar")
        self.assertIsNone(self.state_service.get_pending_episode_request(1001))

    async def test_perfect_clears_pending_sync(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = self.write_pending_sync_file(temp_dir)
            self.state_service.store_pending_sync_request(
                1001,
                self.pending_sync_request(file_path),
            )
            update = build_update(user_id=1001, text="perfect")

            await handle_text_message(update, None)

        update.message.reply_text.assert_awaited_once_with("Great. Enjoy the movie 🎬")
        self.assertIsNone(self.state_service.get_pending_sync_request(1001))

    async def test_amount_reply_after_direction_applies_sync(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = self.write_pending_sync_file(temp_dir)
            self.state_service.store_pending_sync_request(
                1001,
                self.pending_sync_request(file_path, direction="early"),
            )
            update = build_update(user_id=1001, text="2s")

            await handle_text_message(update, None)

        update.message.reply_document.assert_awaited_once()
        sent_file = update.message.reply_document.await_args.kwargs["filename"]
        self.assertEqual(sent_file, "subtitle.synced.srt")
        self.assertIsNone(self.state_service.get_pending_sync_request(1001))

    async def test_expired_sync_request_replies_with_expiry_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = self.write_pending_sync_file(temp_dir)
            self.state_service.store_pending_sync_request(
                1001,
                self.pending_sync_request(
                    file_path,
                    created_at=datetime.now(timezone.utc) - timedelta(minutes=31),
                ),
            )
            update = build_update(user_id=1001, text="2s early")

            await handle_text_message(update, None)

        update.message.reply_text.assert_awaited_once_with(
            "That subtitle session expired. Download the subtitle again to sync it."
        )
        self.assertIsNone(self.state_service.get_pending_sync_request(1001))

    def pending_request(self) -> PendingEpisodeRequest:
        return PendingEpisodeRequest(
            tmdb_id=1399,
            title="Game of Thrones",
            original_query="GOT",
            normalized_title="Game of Thrones",
            year=2011,
            created_at=datetime.now(timezone.utc),
        )

    def pending_sync_request(
        self,
        file_path: Path,
        direction: str | None = None,
        created_at: datetime | None = None,
    ) -> PendingSyncRequest:
        return PendingSyncRequest(
            file_path=file_path,
            original_file_name="subtitle.srt",
            created_at=created_at or datetime.now(timezone.utc),
            direction=direction,
        )

    def write_pending_sync_file(self, temp_dir: str) -> Path:
        file_path = Path(temp_dir) / "subtitle.srt"
        file_path.write_text(
            "1\n00:00:01,000 --> 00:00:02,000\nHi\n",
            encoding="utf-8",
        )
        return file_path


def build_update(user_id: int, text: str = "") -> SimpleNamespace:
    """Build a minimal Telegram update stand-in for text handler tests."""
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(
            text=text,
            reply_text=AsyncMock(),
            reply_document=AsyncMock(),
        ),
    )


if __name__ == "__main__":
    unittest.main()
