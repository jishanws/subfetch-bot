"""Tests for smart title resolution."""

import unittest

from bot.models.search_result import SearchResult
from bot.services.tmdb_service import TmdbNoResultsError
from bot.services.title_resolution_service import TitleResolutionService


class FakeTmdbService:
    """Small fake TMDb service keyed by normalized query."""

    def __init__(self, results_by_query: dict[str, list[SearchResult]]) -> None:
        self.results_by_query = results_by_query
        self.queries: list[str] = []

    def multi_search(self, query: str) -> list[SearchResult]:
        self.queries.append(query)
        results = self.results_by_query.get(query.lower())
        if not results:
            raise TmdbNoResultsError("No results.")
        return results


class FakeGroqService:
    """Fake Groq correction service."""

    def __init__(self, corrected_query: str | None) -> None:
        self.corrected_query = corrected_query
        self.calls: list[str] = []

    def correct_title(self, query: str) -> str | None:
        self.calls.append(query)
        return self.corrected_query


class TitleResolutionServiceTests(unittest.TestCase):
    """Title resolution unit tests."""

    def test_tv_title_without_episode_needs_episode(self) -> None:
        service = TitleResolutionService(
            tmdb_service=FakeTmdbService({"breaking bad": [self.tv_result("Breaking Bad", 2008)]}),
            groq_service=FakeGroqService(None),
        )

        resolution = service.resolve_user_query("Breaking Bad")

        self.assertTrue(resolution.needs_episode)
        self.assertEqual(resolution.media_type, "tv")
        self.assertEqual(resolution.title, "Breaking Bad")
        self.assertIsNone(resolution.season)
        self.assertIsNone(resolution.episode)

    def test_tv_title_with_episode_does_not_need_episode(self) -> None:
        service = TitleResolutionService(
            tmdb_service=FakeTmdbService({"breaking bad": [self.tv_result("Breaking Bad", 2008)]}),
            groq_service=FakeGroqService(None),
        )

        resolution = service.resolve_user_query("Breaking Bad S02E05")

        self.assertFalse(resolution.needs_episode)
        self.assertEqual(resolution.season, 2)
        self.assertEqual(resolution.episode, 5)
        self.assertEqual(resolution.normalized_query, "Breaking Bad season 2 episode 5")

    def test_dark_episode_does_not_need_episode(self) -> None:
        service = TitleResolutionService(
            tmdb_service=FakeTmdbService({"dark": [self.tv_result("Dark", 2017)]}),
            groq_service=FakeGroqService(None),
        )

        resolution = service.resolve_user_query("Dark S01E03")

        self.assertFalse(resolution.needs_episode)
        self.assertEqual(resolution.season, 1)
        self.assertEqual(resolution.episode, 3)
        self.assertEqual(resolution.normalized_query, "Dark season 1 episode 3")

    def test_groq_fallback_returns_corrected_query(self) -> None:
        groq_service = FakeGroqService("the shawshank redemption")
        service = TitleResolutionService(
            tmdb_service=FakeTmdbService(
                {
                    "the shawshank redemption": [
                        self.movie_result("The Shawshank Redemption", 1994)
                    ]
                }
            ),
            groq_service=groq_service,
        )

        resolution = service.resolve_user_query("The shawshank redemtion")

        self.assertEqual(groq_service.calls, ["The shawshank redemtion"])
        self.assertEqual(resolution.title, "The Shawshank Redemption")
        self.assertEqual(resolution.normalized_query, "The Shawshank Redemption 1994")
        self.assertEqual(resolution.media_type, "movie")

    def test_groq_is_not_called_when_tmdb_search_succeeds(self) -> None:
        groq_service = FakeGroqService("unused")
        service = TitleResolutionService(
            tmdb_service=FakeTmdbService(
                {"interstellar": [self.movie_result("Interstellar", 2014)]}
            ),
            groq_service=groq_service,
        )

        resolution = service.resolve_user_query("interstellar")

        self.assertEqual(groq_service.calls, [])
        self.assertEqual(resolution.normalized_query, "Interstellar 2014")

    def test_got_alias_resolves_to_game_of_thrones(self) -> None:
        service = TitleResolutionService(
            tmdb_service=FakeTmdbService(
                {
                    "game of thrones": [
                        self.tv_result("We Got Married", 2008),
                        self.tv_result("Game of Thrones", 2011),
                    ]
                }
            ),
            groq_service=FakeGroqService(None),
        )

        resolution = service.resolve_user_query("GOT")

        self.assertEqual(resolution.title, "Game of Thrones")
        self.assertTrue(resolution.needs_episode)

    def test_game_of_throne_alias_resolves_to_game_of_thrones(self) -> None:
        service = TitleResolutionService(
            tmdb_service=FakeTmdbService(
                {"game of thrones": [self.tv_result("Game of Thrones", 2011)]}
            ),
            groq_service=FakeGroqService(None),
        )

        resolution = service.resolve_user_query("game of throne")

        self.assertEqual(resolution.title, "Game of Thrones")
        self.assertTrue(resolution.needs_episode)

    def movie_result(self, title: str, year: int) -> SearchResult:
        return SearchResult(
            tmdb_id=1,
            title=title,
            release_year=year,
            media_type="movie",
            overview="",
            poster_path=None,
        )

    def tv_result(self, title: str, year: int) -> SearchResult:
        return SearchResult(
            tmdb_id=2,
            title=title,
            release_year=year,
            media_type="tv",
            overview="",
            poster_path=None,
        )


if __name__ == "__main__":
    unittest.main()
