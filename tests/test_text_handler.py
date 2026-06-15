"""Tests for natural-language text handler state handling."""

from datetime import datetime, timezone
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot.handlers.text import handle_pending_episode_reply, handle_text_message
from bot.services.conversation_state_service import (
    ConversationStateService,
    PendingEpisodeRequest,
    pending_episode_requests,
)


class TextHandlerPendingEpisodeTests(unittest.IsolatedAsyncioTestCase):
    """Pending TV episode reply tests."""

    def setUp(self) -> None:
        pending_episode_requests.clear()
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

    def pending_request(self) -> PendingEpisodeRequest:
        return PendingEpisodeRequest(
            tmdb_id=1399,
            title="Game of Thrones",
            original_query="GOT",
            normalized_title="Game of Thrones",
            year=2011,
            created_at=datetime.now(timezone.utc),
        )


def build_update(user_id: int, text: str = "") -> SimpleNamespace:
    """Build a minimal Telegram update stand-in for text handler tests."""
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(text=text, reply_text=AsyncMock()),
    )


if __name__ == "__main__":
    unittest.main()
