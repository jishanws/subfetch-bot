"""Tests for deterministic natural-language intent classification."""

import unittest

from bot.services.intent_service import Intent, IntentService


class IntentServiceTests(unittest.TestCase):
    """Intent service unit tests."""

    def setUp(self) -> None:
        self.service = IntentService()

    def test_help_messages(self) -> None:
        self.assert_intent("help", Intent.HELP, "")
        self.assert_intent("what can you do?", Intent.HELP, "")

    def test_subtitle_terms_find_subtitle(self) -> None:
        self.assert_intent("interstellar subtitle", Intent.FIND_SUBTITLE, "interstellar")
        self.assert_intent(
            "find subtitle for breaking bad season 2 episode 5",
            Intent.FIND_SUBTITLE,
            "breaking bad season 2 episode 5",
        )
        self.assert_intent(
            "dark s01e03 english subtitle",
            Intent.FIND_SUBTITLE,
            "dark season 1 episode 3 english",
        )
        self.assert_intent("avatar 2009 subtitle", Intent.FIND_SUBTITLE, "avatar 2009")

    def test_episode_patterns_find_subtitle_without_subtitle_term(self) -> None:
        self.assert_intent(
            "Dark s01 E03",
            Intent.FIND_SUBTITLE,
            "dark season 1 episode 3",
        )
        self.assert_intent(
            "dark s01e03",
            Intent.FIND_SUBTITLE,
            "dark season 1 episode 3",
        )
        self.assert_intent(
            "breaking bad s2e5",
            Intent.FIND_SUBTITLE,
            "breaking bad season 2 episode 5",
        )
        self.assert_intent(
            "breaking bad season 2 episode 5",
            Intent.FIND_SUBTITLE,
            "breaking bad season 2 episode 5",
        )

    def test_search_prefixes_search_title(self) -> None:
        self.assert_intent("search breaking bad", Intent.SEARCH_TITLE, "breaking bad")
        self.assert_intent("find movie avatar", Intent.SEARCH_TITLE, "avatar")
        self.assert_intent("tv dark", Intent.SEARCH_TITLE, "dark")

    def test_plain_title_defaults_to_find_subtitle(self) -> None:
        self.assert_intent("interstellar", Intent.FIND_SUBTITLE, "interstellar")
        self.assert_intent(
            "breaking bad season 2 episode 5",
            Intent.FIND_SUBTITLE,
            "breaking bad season 2 episode 5",
        )

    def test_empty_action_queries_are_unknown(self) -> None:
        self.assert_intent("search", Intent.UNKNOWN, "")
        self.assert_intent("subtitle", Intent.UNKNOWN, "")
        self.assert_intent("1", Intent.UNKNOWN, "")

    def assert_intent(self, message: str, intent: Intent, query: str) -> None:
        result = self.service.classify(message)

        self.assertIs(result.intent, intent)
        self.assertEqual(result.query, query)


if __name__ == "__main__":
    unittest.main()
