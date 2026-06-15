"""Tests for search response formatting."""

import unittest

from bot.handlers.search import format_search_results
from bot.models.search_result import SearchResult


class SearchHandlerTests(unittest.TestCase):
    """Search handler unit tests."""

    def test_format_search_results(self) -> None:
        results = [
            SearchResult(
                tmdb_id=1396,
                title="Breaking Bad",
                release_year=2008,
                media_type="tv",
                overview="",
                poster_path="/poster.jpg",
            ),
            SearchResult(
                tmdb_id=123,
                title="Breaking Bad Movie",
                release_year=2023,
                media_type="movie",
                overview="",
                poster_path=None,
            ),
        ]

        self.assertEqual(
            format_search_results(results),
            "1. Breaking Bad (2008)\n"
            "TV Show\n\n"
            "2. Breaking Bad Movie (2023)\n"
            "Movie",
        )


if __name__ == "__main__":
    unittest.main()

