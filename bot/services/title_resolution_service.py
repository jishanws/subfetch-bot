"""Resolve user title queries through TMDb with minimal Groq fallback."""

from dataclasses import dataclass
import logging
import re
from typing import Literal

from bot.models.search_result import SearchResult
from bot.services.alias_service import AliasService
from bot.services.groq_service import GroqService, GroqServiceError
from bot.services.tmdb_service import TmdbNoResultsError, TmdbService

logger = logging.getLogger(__name__)

MediaType = Literal["movie", "tv", "unknown"]


@dataclass(frozen=True)
class TitleResolution:
    """Resolved title metadata and subtitle search query."""

    normalized_query: str
    media_type: MediaType
    tmdb_id: int | None
    title: str
    year: int | None
    needs_episode: bool
    season: int | None
    episode: int | None


class TitleResolutionService:
    """Resolve raw user text into title metadata for subtitle search."""

    COMPACT_EPISODE_PATTERN = re.compile(
        r"\bs0*(?P<season>\d{1,2})\s*e0*(?P<episode>\d{1,3})\b",
        flags=re.IGNORECASE,
    )
    SEASON_EPISODE_PATTERN = re.compile(
        r"\bseason\s+0*(?P<season>\d{1,2})\s+"
        r"(?:episode|ep)\s+0*(?P<episode>\d{1,3})\b",
        flags=re.IGNORECASE,
    )
    EPISODE_OF_SEASON_PATTERN = re.compile(
        r"\bepisode\s+0*(?P<episode>\d{1,3})\s+of\s+season\s+"
        r"0*(?P<season>\d{1,2})\b",
        flags=re.IGNORECASE,
    )
    SUBTITLE_WORD_PATTERN = re.compile(
        r"\b(?:subtitle|subtitles|sub|subs|srt|caption|captions)\b",
        flags=re.IGNORECASE,
    )

    def __init__(
        self,
        tmdb_service: TmdbService,
        groq_service: GroqService | None = None,
        alias_service: AliasService | None = None,
    ) -> None:
        self._tmdb_service = tmdb_service
        self._groq_service = groq_service
        self._alias_service = alias_service or AliasService()

    def resolve_user_query(self, raw_text: str) -> TitleResolution:
        """Resolve a user query through TMDb, retrying once with Groq if needed."""
        season, episode = self._extract_episode(raw_text)
        tmdb_query = self._build_tmdb_query(raw_text)

        try:
            result = self._best_tmdb_result(tmdb_query)
        except TmdbNoResultsError:
            corrected_query = self._correct_with_groq(tmdb_query)
            if corrected_query is None or corrected_query.lower() == tmdb_query.lower():
                raise

            logger.info(
                "Retrying TMDb search with Groq correction original_query=%s corrected_query=%s",
                tmdb_query,
                corrected_query,
            )
            result = self._best_tmdb_result(corrected_query)

        return self._build_resolution(result, season, episode)

    def _best_tmdb_result(self, query: str) -> SearchResult:
        results = self._tmdb_service.multi_search(query)
        normalized_query = self._normalize_title(query)
        for result in results:
            if self._normalize_title(result.title) == normalized_query:
                return result
        return results[0]

    def _correct_with_groq(self, query: str) -> str | None:
        if self._groq_service is None:
            return None

        logger.info("Using Groq fallback for title correction original_query=%s", query)
        try:
            corrected_query = self._groq_service.correct_title(query)
        except GroqServiceError:
            logger.exception("Groq fallback failed original_query=%s", query)
            return None

        logger.info(
            "Groq fallback title correction original_query=%s corrected_query=%s",
            query,
            corrected_query,
        )
        return corrected_query

    def _build_resolution(
        self,
        result: SearchResult,
        season: int | None,
        episode: int | None,
    ) -> TitleResolution:
        needs_episode = result.media_type == "tv" and (season is None or episode is None)
        normalized_query = self._build_subtitle_query(result, season, episode)

        return TitleResolution(
            normalized_query=normalized_query,
            media_type=result.media_type,
            tmdb_id=result.tmdb_id,
            title=result.title,
            year=result.release_year,
            needs_episode=needs_episode,
            season=season,
            episode=episode,
        )

    def _build_subtitle_query(
        self,
        result: SearchResult,
        season: int | None,
        episode: int | None,
    ) -> str:
        if result.media_type == "tv" and season is not None and episode is not None:
            return f"{result.title} season {season} episode {episode}"
        if result.release_year:
            return f"{result.title} {result.release_year}"
        return result.title

    def _build_tmdb_query(self, raw_text: str) -> str:
        query = self.SUBTITLE_WORD_PATTERN.sub(" ", raw_text)
        query = self.COMPACT_EPISODE_PATTERN.sub(" ", query)
        query = self.SEASON_EPISODE_PATTERN.sub(" ", query)
        query = self.EPISODE_OF_SEASON_PATTERN.sub(" ", query)
        query = re.sub(r"[?:!,]+", " ", query)
        query = re.sub(r"\s+", " ", query).strip()
        return self._alias_service.resolve(query)

    def _extract_episode(self, raw_text: str) -> tuple[int | None, int | None]:
        for pattern in (
            self.COMPACT_EPISODE_PATTERN,
            self.SEASON_EPISODE_PATTERN,
            self.EPISODE_OF_SEASON_PATTERN,
        ):
            match = pattern.search(raw_text)
            if match is not None:
                return int(match.group("season")), int(match.group("episode"))

        return None, None

    def _normalize_title(self, title: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", " ", title.lower())
        return re.sub(r"\s+", " ", normalized).strip()
