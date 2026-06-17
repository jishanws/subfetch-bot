"""Tests for subtitle providers and aggregator."""

import unittest
from unittest.mock import MagicMock, patch

from bot.models.subtitle_result import SubtitleDownload, SubtitleResult
from bot.services.subtitle_aggregator_service import SubtitleAggregatorService
from bot.services.subtitle_providers.subdl_provider import SubdlProvider
from bot.services.subtitle_providers.opensubtitles_provider import OpenSubtitlesProvider


class SubdlProviderTests(unittest.TestCase):
    def setUp(self):
        self.provider = SubdlProvider(api_key="test_key")

    @patch("requests.Session.get")
    def test_successful_search_maps_results(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": True,
            "subtitles": [
                {
                    "release_name": "Test.Release.1080p",
                    "name": "Test.Release.1080p.srt",
                    "language": "EN",
                    "url": "/subtitle/test.zip",
                    "hi": False
                }
            ]
        }
        mock_get.return_value = mock_response

        results = self.provider.search_subtitles(query="test", language="en")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source, "subdl")
        self.assertEqual(results[0].release_name, "Test.Release.1080p")
        self.assertEqual(results[0].download_url, "https://dl.subdl.com/subtitle/test.zip")
        self.assertEqual(results[0].provider_subtitle_id, "/subtitle/test.zip")

    @patch("requests.Session.get")
    def test_no_results(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": True,
            "subtitles": []
        }
        mock_get.return_value = mock_response

        results = self.provider.search_subtitles(query="test", language="en")
        self.assertEqual(len(results), 0)

    @patch("requests.Session.get")
    def test_api_failure_returns_empty(self, mock_get):
        mock_get.side_effect = Exception("API Error")

        results = self.provider.search_subtitles(query="test", language="en")
        self.assertEqual(len(results), 0)


class AggregatorTests(unittest.TestCase):
    def setUp(self):
        self.mock_os = MagicMock(spec=OpenSubtitlesProvider)
        self.mock_os.name = "opensubtitles"
        self.mock_sd = MagicMock(spec=SubdlProvider)
        self.mock_sd.name = "subdl"
        
        self.aggregator = SubtitleAggregatorService([self.mock_os, self.mock_sd])

    def test_calls_both_providers_and_merges(self):
        self.mock_os.search_subtitles.return_value = [
            SubtitleResult(subtitle_id="1", file_id="1", language="en", file_name="os.srt", download_count=100, source="opensubtitles", release_name="OS Release")
        ]
        self.mock_sd.search_subtitles.return_value = [
            SubtitleResult(subtitle_id="2", file_id="2", language="en", file_name="sd.srt", download_count=50, source="subdl", release_name="SD Release")
        ]
        
        results = self.aggregator.search_subtitles(query="test")
        
        self.mock_os.search_subtitles.assert_called_once()
        self.mock_sd.search_subtitles.assert_called_once()
        self.assertEqual(len(results), 2)

    def test_continues_if_one_provider_fails(self):
        self.mock_os.search_subtitles.side_effect = Exception("OS Down")
        self.mock_sd.search_subtitles.return_value = [
            SubtitleResult(subtitle_id="2", file_id="2", language="en", file_name="sd.srt", download_count=50, source="subdl", release_name="SD Release")
        ]
        
        results = self.aggregator.search_subtitles(query="test")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source, "subdl")

    def test_deduplicates_duplicate_release_names(self):
        self.mock_os.search_subtitles.return_value = [
            SubtitleResult(subtitle_id="1", file_id="1", language="en", file_name="dup.srt", download_count=100, source="opensubtitles", release_name="Duplicate Release 1080p")
        ]
        self.mock_sd.search_subtitles.return_value = [
            SubtitleResult(subtitle_id="2", file_id="2", language="en", file_name="dup2.srt", download_count=50, source="subdl", release_name="Duplicate Release 1080p")
        ]
        
        results = self.aggregator.search_subtitles(query="test")
        self.assertEqual(len(results), 1)

    def test_top_10_limit_respected(self):
        os_results = []
        for i in range(15):
            os_results.append(SubtitleResult(subtitle_id=str(i), file_id=str(i), language="en", file_name=f"file{i}.srt", download_count=100-i, source="opensubtitles", release_name=f"Release {i}"))
        self.mock_os.search_subtitles.return_value = os_results
        self.mock_sd.search_subtitles.return_value = []
        
        results = self.aggregator.search_subtitles(query="test")
        self.assertEqual(len(results), 10)

    def test_download_routes_to_correct_provider(self):
        # We need to run a search first to populate the cache
        self.mock_os.search_subtitles.return_value = [
            SubtitleResult(subtitle_id="1", file_id="os_file", language="en", file_name="os.srt", download_count=100, source="opensubtitles", release_name="OS Release", provider_subtitle_id="os_prov_id")
        ]
        self.mock_sd.search_subtitles.return_value = [
            SubtitleResult(subtitle_id="2", file_id="sd_file", language="en", file_name="sd.srt", download_count=50, source="subdl", release_name="SD Release", provider_subtitle_id="sd_prov_id")
        ]
        
        results = self.aggregator.search_subtitles(query="test")
        os_result = next(r for r in results if r.source == "opensubtitles")
        sd_result = next(r for r in results if r.source == "subdl")
        
        self.mock_os.download_subtitle.return_value = SubtitleDownload(file_name="os.srt", content=b"os")
        self.mock_sd.download_subtitle.return_value = SubtitleDownload(file_name="sd.srt", content=b"sd")
        
        os_download = self.aggregator.download_subtitle(os_result.file_id)
        self.mock_os.download_subtitle.assert_called_with("os_prov_id")
        self.assertEqual(os_download.content, b"os")
        
        sd_download = self.aggregator.download_subtitle(sd_result.file_id)
        self.mock_sd.download_subtitle.assert_called_with("sd_prov_id")
        self.assertEqual(sd_download.content, b"sd")

