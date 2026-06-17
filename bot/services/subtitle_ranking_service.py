"""Ranking and display helpers for subtitle search results."""

from dataclasses import dataclass
import math
import re

from bot.models.subtitle_result import SubtitleResult

NOISE_TERMS = (
    "trailer",
    "teaser",
    "commentary",
    "behind the scenes",
    "behind.the.scenes",
    "behind-the-scenes",
    "featurette",
    "interview",
    "sample",
    "forced only",
    "forced.only",
    "forced-only",
)
SOURCE_PRIORITY = {
    "BluRay": 70,
    "WEB-DL": 60,
    "WEBRip": 50,
    "HDTV": 40,
    "DVDRip": 30,
    "Unknown": 0,
}
RESOLUTION_PRIORITY = {
    "1080p": 90,
    "720p": 80,
    "4K": 75,
    "Unknown": 0,
}


@dataclass(frozen=True)
class QueryFeatures:
    """Normalized ranking features extracted from the user's query."""

    title: str
    year: str | None
    season: int | None
    episode: int | None


class SubtitleRankingService:
    """Sort subtitle results for user convenience."""

    YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
    COMPACT_EPISODE_PATTERN = re.compile(
        r"\bs0*(?P<season>\d{1,2})\s*e0*(?P<episode>\d{1,3})\b",
        flags=re.IGNORECASE,
    )
    SEASON_EPISODE_PATTERN = re.compile(
        r"\bseason\s+0*(?P<season>\d{1,2})\s+episode\s+0*(?P<episode>\d{1,3})\b",
        flags=re.IGNORECASE,
    )

    def rank(
        self,
        results: list[SubtitleResult],
        query: str,
    ) -> list[SubtitleResult]:
        """Return subtitle results sorted by relevance and quality."""
        if not results:
            return []

        candidates = self._filter_hearing_impaired_only(results)
        features = self._extract_query_features(query)

        return sorted(
            candidates,
            key=lambda result: self._score(result, features),
            reverse=True,
        )

    def _score(self, result: SubtitleResult, query: QueryFeatures) -> tuple[float, ...]:
        result_text = self._normalized_result_text(result)
        title_score = self._title_score(query.title, result_text)
        episode_score = self._episode_score(query, result_text)
        year_score = self._year_score(query.year, result_text)
        language_score = 1.0 if result.language.lower() in {"en", "eng"} else 0.0
        noise_score = -1.0 if is_noisy_result(result) else 0.0
        resolution = detect_resolution(result.release_name or result.file_name)
        source = detect_source(result.release_name or result.file_name)

        return (
            title_score,
            episode_score,
            year_score,
            language_score,
            noise_score,
            RESOLUTION_PRIORITY[resolution],
            SOURCE_PRIORITY[source],
            math.log10(result.download_count + 1),
        )

    def _extract_query_features(self, query: str) -> QueryFeatures:
        normalized_query = self._normalize_text(query)
        year_match = self.YEAR_PATTERN.search(normalized_query)
        episode_match = self.COMPACT_EPISODE_PATTERN.search(
            normalized_query
        ) or self.SEASON_EPISODE_PATTERN.search(normalized_query)

        title = self.YEAR_PATTERN.sub(" ", normalized_query)
        title = self.COMPACT_EPISODE_PATTERN.sub(" ", title)
        title = self.SEASON_EPISODE_PATTERN.sub(" ", title)
        title = re.sub(r"\bsubtitle(?:s)?\b", " ", title)
        title = re.sub(r"\s+", " ", title).strip()

        season = int(episode_match.group("season")) if episode_match else None
        episode = int(episode_match.group("episode")) if episode_match else None

        return QueryFeatures(
            title=title,
            year=year_match.group(0) if year_match else None,
            season=season,
            episode=episode,
        )

    def _title_score(self, title: str, result_text: str) -> float:
        if not title:
            return 0.0
        if title in result_text:
            return 2.0

        title_words = title.split()
        if not title_words:
            return 0.0

        matched_words = sum(1 for word in title_words if re.search(rf"\b{re.escape(word)}\b", result_text))
        return matched_words / len(title_words)

    def _year_score(self, year: str | None, result_text: str) -> float:
        if year is None:
            return 0.0
        return 1.0 if re.search(rf"\b{year}\b", result_text) else -1.0

    def _episode_score(self, query: QueryFeatures, result_text: str) -> float:
        if query.season is None or query.episode is None:
            return 0.0

        compact_pattern = re.compile(
            rf"\bs0*{query.season}\s*e0*{query.episode}\b",
            flags=re.IGNORECASE,
        )
        season_episode_pattern = re.compile(
            rf"\bseason\s+0*{query.season}\s+episode\s+0*{query.episode}\b",
            flags=re.IGNORECASE,
        )

        return 1.0 if compact_pattern.search(result_text) or season_episode_pattern.search(result_text) else -1.0

    def _normalized_result_text(self, result: SubtitleResult) -> str:
        return self._normalize_text(f"{result.release_name} {result.file_name}")

    def _normalize_text(self, text: str) -> str:
        normalized = text.lower()
        normalized = re.sub(r"[._\-]+", " ", normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    def _filter_hearing_impaired_only(
        self,
        results: list[SubtitleResult],
    ) -> list[SubtitleResult]:
        normal_results = [result for result in results if not result.hearing_impaired]
        return normal_results or results


def detect_resolution(text: str) -> str:
    """Detect the primary video resolution from release or file text."""
    normalized = text.lower()
    if re.search(r"\b(?:2160p|4k|uhd)\b", normalized):
        return "4K"
    if re.search(r"\b1080p\b", normalized):
        return "1080p"
    if re.search(r"\b720p\b", normalized):
        return "720p"
    return "Unknown"


def detect_source(text: str) -> str:
    """Detect the primary release source from release or file text."""
    normalized = text.lower()
    if re.search(r"\b(?:blu[\s._-]?ray|bdrip|br ?rip)\b", normalized):
        return "BluRay"
    if re.search(r"\b(?:web[\s._-]?dl|webdl)\b", normalized):
        return "WEB-DL"
    if re.search(r"\bweb[\s._-]?rip\b", normalized):
        return "WEBRip"
    if re.search(r"\bhdtv\b", normalized):
        return "HDTV"
    if re.search(r"\bdvd[\s._-]?rip\b", normalized):
        return "DVDRip"
    return "Unknown"


def format_download_count(count: int) -> str:
    """Format download count for compact Telegram button labels."""
    if count >= 1000:
        value = count / 1000
        if count % 1000 == 0:
            return f"{int(value)}k downloads"
        return f"{value:.1f}k downloads"
    return f"{count} downloads"


def is_noisy_result(result: SubtitleResult) -> bool:
    """Return whether a subtitle result looks like non-primary video content."""
    text = f"{result.release_name} {result.file_name}".lower()
    normalized = re.sub(r"[._\-]+", " ", text)
    return any(term.replace(".", " ").replace("-", " ") in normalized for term in NOISE_TERMS)
