"""Deterministic subtitle sync intent classification."""

from dataclasses import dataclass
from enum import Enum
import logging
import re
from typing import Protocol

logger = logging.getLogger(__name__)


class SyncIntent(str, Enum):
    """Supported subtitle sync reply intents."""

    PERFECT = "PERFECT"
    TOO_EARLY = "TOO_EARLY"
    TOO_LATE = "TOO_LATE"
    NEED_AMOUNT = "NEED_AMOUNT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SyncIntentResult:
    """Classified sync intent and optional timing amount."""

    intent: SyncIntent
    amount_seconds: float | None = None


class SyncGroqFallback(Protocol):
    """Groq fallback shape used by the sync intent service."""

    def classify_sync_message(self, message: str) -> str:
        """Classify a sync message as perfect, early, late, or unknown."""


class SyncIntentService:
    """Classify subtitle sync replies with deterministic rules first."""

    AMOUNT_PATTERN = re.compile(
        r"\b(?P<amount>\d+(?:\.\d+)?)\s*(?:s|sec|secs|second|seconds)\b",
        flags=re.IGNORECASE,
    )
    PERFECT_PATTERN = re.compile(
        r"\b(?:perfect|ok|okay|fine|works|matched|sync(?:ed)?|good)\b",
        flags=re.IGNORECASE,
    )
    EARLY_PATTERN = re.compile(
        r"\b(?:too\s+fast|too\s+early|early|fast|before\s+(?:the\s+)?dialogue|"
        r"subs?\s+ahead|subtitles?\s+(?:appear|are|is)\s+before)\b",
        flags=re.IGNORECASE,
    )
    LATE_PATTERN = re.compile(
        r"\b(?:too\s+slow|too\s+late|late|slow|after\s+(?:the\s+)?dialogue|"
        r"subs?\s+behind|subtitles?\s+(?:appear|are|is)\s+after)\b",
        flags=re.IGNORECASE,
    )

    def __init__(self, groq_service: SyncGroqFallback | None = None) -> None:
        self._groq_service = groq_service

    def classify(self, message: str) -> SyncIntentResult:
        """Classify a subtitle sync reply."""
        deterministic_result = self._classify_deterministic(message)
        if deterministic_result.intent is not SyncIntent.UNKNOWN:
            return deterministic_result

        if self._groq_service is None:
            return deterministic_result

        logger.info("Using Groq fallback for sync intent message=%s", message)
        try:
            groq_intent = self._groq_service.classify_sync_message(message)
        except Exception:
            logger.exception("Groq sync intent fallback failed.")
            return deterministic_result

        return self._map_groq_intent(groq_intent)

    def _classify_deterministic(self, message: str) -> SyncIntentResult:
        normalized = re.sub(r"\s+", " ", message).strip().lower()
        if not normalized:
            return SyncIntentResult(SyncIntent.UNKNOWN)

        amount = self._extract_amount(normalized)
        has_early = bool(self.EARLY_PATTERN.search(normalized))
        has_late = bool(self.LATE_PATTERN.search(normalized))

        if self.PERFECT_PATTERN.search(normalized):
            return SyncIntentResult(SyncIntent.PERFECT)
        if has_early:
            return SyncIntentResult(SyncIntent.TOO_EARLY, amount)
        if has_late:
            return SyncIntentResult(SyncIntent.TOO_LATE, amount)
        if amount is not None:
            return SyncIntentResult(SyncIntent.NEED_AMOUNT, amount)
        return SyncIntentResult(SyncIntent.UNKNOWN)

    def _extract_amount(self, message: str) -> float | None:
        match = self.AMOUNT_PATTERN.search(message)
        if match is None:
            return None
        return float(match.group("amount"))

    def _map_groq_intent(self, groq_intent: str) -> SyncIntentResult:
        normalized = groq_intent.strip().lower()
        if normalized == "perfect":
            return SyncIntentResult(SyncIntent.PERFECT)
        if normalized == "early":
            return SyncIntentResult(SyncIntent.TOO_EARLY)
        if normalized == "late":
            return SyncIntentResult(SyncIntent.TOO_LATE)
        return SyncIntentResult(SyncIntent.UNKNOWN)
