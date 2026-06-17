"""Tests for deterministic title aliases."""

import unittest

from bot.services.alias_service import AliasService


class AliasServiceTests(unittest.TestCase):
    """Alias resolver unit tests."""

    def setUp(self) -> None:
        self.service = AliasService()

    def test_common_aliases_resolve_case_insensitively(self) -> None:
        examples = {
            "GOT": "game of thrones",
            "hotd": "house of the dragon",
            "BB": "breaking bad",
            "tbbt": "the big bang theory",
            "lotr": "lord of the rings",
            "gotg": "guardians of the galaxy",
            "twd": "the walking dead",
        }

        for query, expected in examples.items():
            with self.subTest(query=query):
                self.assertEqual(self.service.resolve(query), expected)

    def test_non_alias_is_returned_unchanged(self) -> None:
        self.assertEqual(self.service.resolve("Interstellar"), "Interstellar")

    def test_alias_requires_whole_query_match(self) -> None:
        self.assertEqual(self.service.resolve("got subtitle"), "got subtitle")

    def test_punctuation_does_not_block_alias_match(self) -> None:
        self.assertEqual(self.service.resolve("G.O.T."), "game of thrones")

    def test_guardians_alias_resolves(self) -> None:
        self.assertEqual(self.service.resolve("gotg"), "guardians of the galaxy")


if __name__ == "__main__":
    unittest.main()
