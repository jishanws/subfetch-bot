"""Base subtitle provider interface."""

from typing import Protocol

from bot.models.subtitle_result import SubtitleDownload, SubtitleResult


class SubtitleProvider(Protocol):
    """Protocol for a subtitle metadata and download provider."""

    name: str

    def search_subtitles(
        self,
        *,
        query: str,
        tmdb_id: int | None = None,
        imdb_id: str | None = None,
        media_type: str | None = None,
        season: int | None = None,
        episode: int | None = None,
        language: str = "en",
    ) -> list[SubtitleResult]:
        """Search for subtitles matching the given criteria."""

    def download_subtitle(
        self,
        subtitle_id: str,
    ) -> SubtitleDownload:
        """Download the subtitle file for the given provider-specific ID."""
