"""Deterministic natural-language intent classification."""

from dataclasses import dataclass
from enum import Enum
import logging
import re

logger = logging.getLogger(__name__)


class Intent(str, Enum):
    """Supported natural-language message intents."""

    HELP = "HELP"
    SEARCH_TITLE = "SEARCH_TITLE"
    FIND_SUBTITLE = "FIND_SUBTITLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class IntentResult:
    """Classified intent and cleaned query text."""

    intent: Intent
    query: str


class IntentService:
    """Classify user messages with simple deterministic rules."""

    SUBTITLE_TERMS = {"subtitle", "subtitles", "sub", "subs", "srt", "caption", "captions"}
    HELP_MESSAGES = {"help", "what can you do"}
    SEARCH_PREFIX_PATTERN = re.compile(
        r"^(?:search|find\s+movie|find\s+series|find\s+tv|movie|series|tv)\b",
        flags=re.IGNORECASE,
    )
    COMPACT_EPISODE_PATTERN = re.compile(
        r"\bs0*(?P<season>\d{1,2})\s*e0*(?P<episode>\d{1,3})\b",
        flags=re.IGNORECASE,
    )
    SEASON_EPISODE_PATTERN = re.compile(
        r"\bseason\s+0*(?P<season>\d{1,2})\s+episode\s+0*(?P<episode>\d{1,3})\b",
        flags=re.IGNORECASE,
    )
    TITLE_PATTERN = re.compile(r"[a-z0-9]", flags=re.IGNORECASE)

    def classify(self, message: str) -> IntentResult:
        """Classify a Telegram text message and extract a clean query."""
        normalized = self._normalize(message)
        lowered = normalized.lower()
        help_text = re.sub(r"[?.!]+$", "", lowered).strip()

        if not normalized:
            result = IntentResult(Intent.UNKNOWN, "")
        elif help_text in self.HELP_MESSAGES:
            result = IntentResult(Intent.HELP, "")
        elif self._contains_subtitle_term(lowered):
            result = IntentResult(Intent.FIND_SUBTITLE, self._clean_subtitle_query(normalized))
        elif self._contains_episode_pattern(normalized):
            result = IntentResult(Intent.FIND_SUBTITLE, self._clean_subtitle_query(normalized))
        elif self.SEARCH_PREFIX_PATTERN.match(normalized):
            result = IntentResult(Intent.SEARCH_TITLE, self._clean_search_query(normalized))
        elif self._looks_like_title(normalized):
            result = IntentResult(Intent.FIND_SUBTITLE, self._clean_subtitle_query(normalized))
        else:
            result = IntentResult(Intent.UNKNOWN, "")

        if result.intent in {Intent.SEARCH_TITLE, Intent.FIND_SUBTITLE} and not result.query:
            result = IntentResult(Intent.UNKNOWN, "")

        logger.info(
            "Classified natural-language message intent=%s query=%s",
            result.intent.value,
            result.query,
        )
        return result

    def _contains_subtitle_term(self, message: str) -> bool:
        words = set(re.findall(r"[a-z0-9]+", message))
        return bool(words & self.SUBTITLE_TERMS)

    def _contains_episode_pattern(self, message: str) -> bool:
        return bool(
            self.COMPACT_EPISODE_PATTERN.search(message)
            or self.SEASON_EPISODE_PATTERN.search(message)
        )

    def _normalize(self, message: str) -> str:
        return re.sub(r"\s+", " ", message).strip()

    def _clean_search_query(self, message: str) -> str:
        query = self.SEARCH_PREFIX_PATTERN.sub("", message, count=1)
        query = re.sub(r"^\s*for\b", " ", query, flags=re.IGNORECASE)
        return self._clean_common_query_text(query)

    def _clean_subtitle_query(self, message: str) -> str:
        query = message
        query = re.sub(
            r"\b(?:find|get|download|search|show\s+me)?\s*"
            r"(?:subtitle|subtitles|sub|subs|srt|caption|captions)\s+for\b",
            " ",
            query,
            flags=re.IGNORECASE,
        )
        query = re.sub(
            r"\b(?:subtitle|subtitles|sub|subs|srt|caption|captions)\b",
            " ",
            query,
            flags=re.IGNORECASE,
        )
        query = re.sub(
            r"^\s*(?:find|get|download|search|show\s+me)\b",
            " ",
            query,
            flags=re.IGNORECASE,
        )
        query = self._normalize_episode_patterns(query)
        return self._clean_common_query_text(query).lower()

    def _normalize_episode_patterns(self, message: str) -> str:
        query = self.COMPACT_EPISODE_PATTERN.sub(
            lambda match: (
                f"season {int(match.group('season'))} "
                f"episode {int(match.group('episode'))}"
            ),
            message,
        )
        query = self.SEASON_EPISODE_PATTERN.sub(
            lambda match: (
                f"season {int(match.group('season'))} "
                f"episode {int(match.group('episode'))}"
            ),
            query,
        )
        return query

    def _clean_common_query_text(self, message: str) -> str:
        query = re.sub(r"\bplease\b", " ", message, flags=re.IGNORECASE)
        query = re.sub(r"[?:!,]+", " ", query)
        return re.sub(r"\s+", " ", query).strip()

    def _looks_like_title(self, message: str) -> bool:
        if not self.TITLE_PATTERN.search(message):
            return False
        if message.isdigit():
            return False

        words = re.findall(r"[a-z0-9]+", message, flags=re.IGNORECASE)
        return 1 <= len(words) <= 12
