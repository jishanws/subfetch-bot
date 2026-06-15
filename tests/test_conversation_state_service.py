"""Tests for short-term conversation state."""

from datetime import datetime, timedelta, timezone
import unittest

from bot.services.conversation_state_service import (
    ConversationStateService,
    PendingEpisodeRequest,
    pending_episode_requests,
)


class ConversationStateServiceTests(unittest.TestCase):
    """Pending episode request tests."""

    def setUp(self) -> None:
        pending_episode_requests.clear()
        self.service = ConversationStateService()

    def test_tv_show_without_episode_stores_pending_state(self) -> None:
        request = self.pending_request()

        self.service.store_pending_episode_request(1001, request)

        self.assertEqual(
            self.service.get_pending_episode_request(1001),
            request,
        )

    def test_episode_reply_combines_with_pending_show(self) -> None:
        request = self.pending_request()
        self.service.store_pending_episode_request(1001, request)

        episode = self.service.parse_episode("s05 e5")

        self.assertEqual(episode, (5, 5))
        self.assertEqual(
            self.service.build_episode_query(request, *episode),
            "Game of Thrones S05E05",
        )

    def test_pending_state_clears_after_successful_episode_reply(self) -> None:
        self.service.store_pending_episode_request(1001, self.pending_request())

        self.service.clear_pending_episode_request(1001)

        self.assertIsNone(self.service.get_pending_episode_request(1001))

    def test_pending_state_expires_after_10_minutes(self) -> None:
        created_at = datetime.now(timezone.utc) - timedelta(minutes=11)
        self.service.store_pending_episode_request(
            1001,
            self.pending_request(created_at=created_at),
        )

        self.assertIsNone(self.service.get_pending_episode_request(1001))
        self.assertNotIn(1001, pending_episode_requests)

    def test_parse_supported_episode_formats(self) -> None:
        examples = {
            "s05e05": (5, 5),
            "s05 e05": (5, 5),
            "s5e5": (5, 5),
            "s5 e5": (5, 5),
            "season 5 episode 5": (5, 5),
            "season 5 ep 5": (5, 5),
            "episode 5 of season 5": (5, 5),
        }

        for message, expected in examples.items():
            with self.subTest(message=message):
                self.assertEqual(self.service.parse_episode(message), expected)

    def pending_request(
        self,
        created_at: datetime | None = None,
    ) -> PendingEpisodeRequest:
        return PendingEpisodeRequest(
            tmdb_id=1399,
            title="Game of Thrones",
            original_query="GOT",
            normalized_title="Game of Thrones",
            year=2011,
            created_at=created_at or datetime.now(timezone.utc),
        )


if __name__ == "__main__":
    unittest.main()
