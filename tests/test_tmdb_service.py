"""Tests for TMDb service normalization and error handling."""

import unittest
from unittest.mock import Mock

import requests

from bot.services.tmdb_service import (
    InvalidTmdbApiKeyError,
    TmdbNetworkError,
    TmdbNoResultsError,
    TmdbService,
)


class TmdbServiceTests(unittest.TestCase):
    """TMDb service unit tests."""

    def test_multi_search_normalizes_movie_and_tv_results(self) -> None:
        session = Mock()
        response = Mock(status_code=200)
        response.json.return_value = {
            "results": [
                {
                    "id": 1396,
                    "media_type": "tv",
                    "name": "Breaking Bad",
                    "first_air_date": "2008-01-20",
                    "overview": "A chemistry teacher becomes a criminal.",
                    "poster_path": "/ggFHVNu6YYI5L9pCfOacjizRGt.jpg",
                },
                {
                    "id": 19995,
                    "media_type": "movie",
                    "title": "Avatar",
                    "release_date": "2009-12-15",
                    "overview": "On Pandora, a paraplegic Marine finds a new life.",
                    "poster_path": "/kyeqWdyUXW608qlYkRqosgbbJyK.jpg",
                },
                {"id": 1, "media_type": "person", "name": "Ignored Person"},
            ]
        }
        session.get.return_value = response

        results = TmdbService("api-key", session=session).multi_search("breaking bad")

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].tmdb_id, 1396)
        self.assertEqual(results[0].title, "Breaking Bad")
        self.assertEqual(results[0].release_year, 2008)
        self.assertEqual(results[0].media_type, "tv")
        self.assertEqual(results[1].media_type, "movie")

    def test_invalid_api_key_raises_domain_error(self) -> None:
        session = Mock()
        session.get.return_value = Mock(status_code=401)

        with self.assertRaises(InvalidTmdbApiKeyError):
            TmdbService("bad-key", session=session).multi_search("avatar")

    def test_no_results_raises_domain_error(self) -> None:
        session = Mock()
        response = Mock(status_code=200)
        response.json.return_value = {"results": []}
        session.get.return_value = response

        with self.assertRaises(TmdbNoResultsError):
            TmdbService("api-key", session=session).multi_search("unknown title")

    def test_network_failure_raises_domain_error(self) -> None:
        session = Mock()
        session.get.side_effect = requests.Timeout("timeout")

        with self.assertRaises(TmdbNetworkError):
            TmdbService("api-key", session=session).multi_search("dark")


if __name__ == "__main__":
    unittest.main()
