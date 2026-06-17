"""Tests for subtitle result ranking."""

import unittest

from bot.models.subtitle_result import SubtitleResult
from bot.services.subtitle_ranking_service import (
    SubtitleRankingService,
    format_download_count,
    is_noisy_result,
)


class SubtitleRankingServiceTests(unittest.TestCase):
    """Subtitle ranking unit tests."""

    def setUp(self) -> None:
        self.service = SubtitleRankingService()

    def test_1080p_ranked_before_720p(self) -> None:
        results = [
            self.result("1", "Dark.S01E03.720p.WEB-DL", downloads=5000),
            self.result("2", "Dark.S01E03.1080p.WEB-DL", downloads=1000),
        ]

        ranked = self.service.rank(results, "dark s01e03")

        self.assertEqual(ranked[0].file_id, "2")

    def test_noisy_trailer_result_pushed_down(self) -> None:
        results = [
            self.result("1", "Dark.S01E03.1080p.BluRay.Trailer", downloads=50000),
            self.result("2", "Dark.S01E03.1080p.BluRay", downloads=1000),
        ]

        ranked = self.service.rank(results, "dark s01e03")

        self.assertTrue(is_noisy_result(ranked[-1]))
        self.assertEqual(ranked[0].file_id, "2")

    def test_higher_downloads_used_as_tie_breaker(self) -> None:
        results = [
            self.result("1", "Dark.S01E03.1080p.WEB-DL", downloads=1000),
            self.result("2", "Dark.S01E03.1080p.WEB-DL", downloads=5000),
        ]

        ranked = self.service.rank(results, "dark s01e03")

        self.assertEqual(ranked[0].file_id, "2")

    def test_correct_episode_beats_higher_quality_wrong_episode(self) -> None:
        results = [
            self.result("1", "Dark.S01E04.1080p.BluRay", downloads=50000),
            self.result("2", "Dark.S01E03.720p.WEB-DL", downloads=1000),
        ]

        ranked = self.service.rank(results, "dark s01e03")

        self.assertEqual(ranked[0].file_id, "2")

    def test_correct_year_beats_higher_quality_wrong_year(self) -> None:
        results = [
            self.result("1", "Avatar.2022.1080p.BluRay", downloads=50000),
            self.result("2", "Avatar.2009.720p.WEB-DL", downloads=1000),
        ]

        ranked = self.service.rank(results, "avatar 2009")

        self.assertEqual(ranked[0].file_id, "2")

    def test_english_ranked_first(self) -> None:
        results = [
            self.result("1", "Dark.S01E03.1080p.WEB-DL", language="bn", downloads=5000),
            self.result("2", "Dark.S01E03.1080p.WEB-DL", language="en", downloads=1000),
        ]

        ranked = self.service.rank(results, "dark s01e03")

        self.assertEqual(ranked[0].file_id, "2")

    def test_hearing_impaired_results_removed_when_normal_exists(self) -> None:
        results = [
            self.result("1", "Dark.S01E03.1080p.WEB-DL.HI", hearing_impaired=True),
            self.result("2", "Dark.S01E03.1080p.WEB-DL", hearing_impaired=False),
        ]

        ranked = self.service.rank(results, "dark s01e03")

        self.assertEqual([result.file_id for result in ranked], ["2"])

    def test_format_download_count(self) -> None:
        self.assertEqual(format_download_count(900), "900 downloads")
        self.assertEqual(format_download_count(12000), "12k downloads")
        self.assertEqual(format_download_count(12500), "12.5k downloads")

    def result(
        self,
        file_id: str,
        release_name: str,
        language: str = "en",
        downloads: int = 1000,
        hearing_impaired: bool = False,
    ) -> SubtitleResult:
        return SubtitleResult(
            subtitle_id=file_id,
            file_id=file_id,
            language=language,
            file_name=f"{release_name}.srt",
            download_count=downloads,
            hearing_impaired=hearing_impaired,
            release_name=release_name,
        )


if __name__ == "__main__":
    unittest.main()
