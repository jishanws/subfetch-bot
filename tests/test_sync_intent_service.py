"""Tests for subtitle sync intent classification."""

import unittest

from bot.services.sync_intent_service import SyncIntent, SyncIntentService


class SyncIntentServiceTests(unittest.TestCase):
    """Sync intent parser tests."""

    def setUp(self) -> None:
        self.service = SyncIntentService()

    def test_too_fast_is_too_early(self) -> None:
        result = self.service.classify("too fast")

        self.assertIs(result.intent, SyncIntent.TOO_EARLY)
        self.assertIsNone(result.amount_seconds)

    def test_too_slow_is_too_late(self) -> None:
        result = self.service.classify("too slow")

        self.assertIs(result.intent, SyncIntent.TOO_LATE)
        self.assertIsNone(result.amount_seconds)

    def test_seconds_early_extracts_amount(self) -> None:
        result = self.service.classify("subtitle is 2 seconds early")

        self.assertIs(result.intent, SyncIntent.TOO_EARLY)
        self.assertEqual(result.amount_seconds, 2)

    def test_seconds_late_extracts_amount(self) -> None:
        result = self.service.classify("3s late")

        self.assertIs(result.intent, SyncIntent.TOO_LATE)
        self.assertEqual(result.amount_seconds, 3)


if __name__ == "__main__":
    unittest.main()
