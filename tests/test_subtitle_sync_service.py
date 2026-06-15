"""Tests for SRT subtitle synchronization."""

import unittest

from bot.services.subtitle_sync_service import SubtitleSyncService


class SubtitleSyncServiceTests(unittest.TestCase):
    """Subtitle sync service tests."""

    def setUp(self) -> None:
        self.service = SubtitleSyncService()

    def test_srt_shift_plus_two_seconds(self) -> None:
        shifted = self.service.shift_srt_content(self.sample_srt(), 2)

        self.assertIn("00:00:03,000 --> 00:00:04,500", shifted)
        self.assertIn("Hello", shifted)

    def test_srt_shift_minus_two_seconds(self) -> None:
        shifted = self.service.shift_srt_content(self.sample_srt(), -2)

        self.assertIn("00:00:00,000 --> 00:00:00,500", shifted)
        self.assertIn("Hello", shifted)

    def test_negative_timestamps_are_clamped_to_zero(self) -> None:
        shifted = self.service.shift_srt_content(self.sample_srt(), -5)

        self.assertIn("00:00:00,000 --> 00:00:00,000", shifted)

    def sample_srt(self) -> str:
        return "1\n00:00:01,000 --> 00:00:02,500\nHello\n"


if __name__ == "__main__":
    unittest.main()
