"""Tests for OpenSubtitles service."""

import unittest
from unittest.mock import Mock

import requests

from bot.services.opensubtitles_service import (
    OpenSubtitlesDownloadLinkExpiredError,
    OpenSubtitlesAuthenticationError,
    OpenSubtitlesDowntimeError,
    OpenSubtitlesFileUnavailableError,
    OpenSubtitlesNoResultsError,
    OpenSubtitlesRateLimitError,
    OpenSubtitlesService,
)


class OpenSubtitlesServiceTests(unittest.TestCase):
    """OpenSubtitles service unit tests."""

    def test_search_subtitles_normalizes_results(self) -> None:
        session = Mock()
        response = Mock(status_code=200)
        response.json.return_value = {
            "data": [
                {
                    "id": "123",
                    "attributes": {
                        "subtitle_id": "abc-123",
                        "language": "en",
                        "download_count": 12000,
                        "hearing_impaired": False,
                        "release": "BluRay",
                        "files": [
                            {
                                "file_id": 456,
                                "file_name": "Avatar.2009.BluRay.srt",
                            }
                        ],
                    },
                }
            ]
        }
        session.get.return_value = response

        results = OpenSubtitlesService("api-key", session=session).search_subtitles(
            "avatar"
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].subtitle_id, "abc-123")
        self.assertEqual(results[0].file_id, "456")
        self.assertEqual(results[0].language, "en")
        self.assertEqual(results[0].file_name, "Avatar.2009.BluRay.srt")
        self.assertEqual(results[0].download_count, 12000)
        self.assertEqual(results[0].release_name, "BluRay")

    def test_search_subtitles_sends_api_key_header(self) -> None:
        session = Mock()
        response = Mock(status_code=200)
        response.json.return_value = {
            "data": [
                {
                    "id": "123",
                    "attributes": {
                        "language": "en",
                        "download_count": 1,
                        "files": [{"file_id": 456, "file_name": "file.srt"}],
                    },
                }
            ]
        }
        session.get.return_value = response

        OpenSubtitlesService("api-key", session=session).search_subtitles("dark")

        headers = session.get.call_args.kwargs["headers"]
        self.assertEqual(headers["Api-Key"], "api-key")
        self.assertEqual(headers["User-Agent"], "subfetch-bot v0.1")

    def test_authenticate_stores_login_token(self) -> None:
        session = Mock()
        response = Mock(status_code=200)
        response.json.return_value = {"token": "token-123"}
        session.post.return_value = response

        service = OpenSubtitlesService("api-key", session=session)

        self.assertEqual(service.authenticate("user", "pass"), "token-123")

    def test_authentication_failure_raises_domain_error(self) -> None:
        session = Mock()
        session.get.return_value = Mock(status_code=401)

        with self.assertRaises(OpenSubtitlesAuthenticationError):
            OpenSubtitlesService("bad-key", session=session).search_subtitles("avatar")

    def test_no_results_raises_domain_error(self) -> None:
        session = Mock()
        response = Mock(status_code=200)
        response.json.return_value = {"data": []}
        session.get.return_value = response

        with self.assertRaises(OpenSubtitlesNoResultsError):
            OpenSubtitlesService("api-key", session=session).search_subtitles("unknown")

    def test_api_downtime_raises_domain_error(self) -> None:
        session = Mock()
        session.get.side_effect = requests.Timeout("timeout")

        with self.assertRaises(OpenSubtitlesDowntimeError):
            OpenSubtitlesService("api-key", session=session).search_subtitles("dark")

    def test_download_subtitle_fetches_temporary_link(self) -> None:
        session = Mock()
        link_response = Mock(status_code=200)
        link_response.json.return_value = {
            "link": "https://downloads.example/subtitle.srt",
            "file_name": "subtitle.srt",
        }
        file_response = Mock(status_code=200, content=b"1\n00:00:01,000 --> 00:00:02,000\nHi\n")
        session.post.return_value = link_response
        session.get.return_value = file_response

        download = OpenSubtitlesService("api-key", session=session).download_subtitle("456")

        self.assertEqual(download.file_name, "subtitle.srt")
        self.assertEqual(download.extension, ".srt")
        self.assertIn(b"Hi", download.content)
        session.post.assert_called_once()
        self.assertEqual(session.post.call_args.kwargs["json"], {"file_id": "456"})

    def test_download_subtitle_rate_limit_raises_domain_error(self) -> None:
        session = Mock()
        session.post.return_value = Mock(status_code=429)

        with self.assertRaises(OpenSubtitlesRateLimitError):
            OpenSubtitlesService("api-key", session=session).download_subtitle("456")

    def test_download_subtitle_expired_link_raises_domain_error(self) -> None:
        session = Mock()
        link_response = Mock(status_code=200)
        link_response.json.return_value = {
            "link": "https://downloads.example/subtitle.srt",
            "file_name": "subtitle.srt",
        }
        file_response = Mock(status_code=410, content=b"")
        session.post.return_value = link_response
        session.get.return_value = file_response

        with self.assertRaises(OpenSubtitlesDownloadLinkExpiredError):
            OpenSubtitlesService("api-key", session=session).download_subtitle("456")

    def test_download_subtitle_unsupported_file_raises_domain_error(self) -> None:
        session = Mock()
        link_response = Mock(status_code=200)
        link_response.json.return_value = {
            "link": "https://downloads.example/subtitle.zip",
            "file_name": "subtitle.zip",
        }
        session.post.return_value = link_response

        with self.assertRaises(OpenSubtitlesFileUnavailableError):
            OpenSubtitlesService("api-key", session=session).download_subtitle("456")


if __name__ == "__main__":
    unittest.main()
