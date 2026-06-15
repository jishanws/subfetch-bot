"""Tests for subtitle response formatting."""

import unittest

from bot.handlers.subtitle import (
    build_tmdb_identification_query,
    format_subtitle_results,
)
from bot.models.subtitle_result import SubtitleResult


class SubtitleHandlerTests(unittest.TestCase):
    """Subtitle handler unit tests."""

    def test_format_subtitle_results(self) -> None:
        results = [
            SubtitleResult(
                subtitle_id="1",
                language="en",
                file_name="file-1.srt",
                download_count=12000,
                hearing_impaired=False,
                release_name="BluRay",
            ),
            SubtitleResult(
                subtitle_id="2",
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


if __name__ == "__main__":
    unittest.main()
