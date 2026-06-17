"""OpenSubtitles provider wrapper."""

import logging

from bot.models.subtitle_result import SubtitleDownload, SubtitleResult
from bot.services.opensubtitles_service import OpenSubtitlesService
from bot.services.subtitle_providers.base import SubtitleProvider

logger = logging.getLogger(__name__)


class OpenSubtitlesProvider(SubtitleProvider):
    """Subtitle provider wrapper for OpenSubtitles."""

    name = "opensubtitles"

    def __init__(self, service: OpenSubtitlesService) -> None:
        self._service = service

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
        """Search OpenSubtitles for subtitles."""
        try:
            results = self._service.search_subtitles(query=query, language=language)
            # Update the provider info for existing results
            for result in results:
                result.source = self.name
                # OpenSubtitles uses `file_id` for downloading, so we use it as provider_subtitle_id
                result.provider_subtitle_id = result.file_id
            return results
        except Exception:
            logger.exception("OpenSubtitles provider search failed.")
            return []

    def download_subtitle(
        self,
        subtitle_id: str,
    ) -> SubtitleDownload:
        """Download subtitle from OpenSubtitles."""
        # Note: OpenSubtitlesService expects the file_id for downloading
        return self._service.download_subtitle(subtitle_id)
