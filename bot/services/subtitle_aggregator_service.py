"""Aggregates subtitle results from multiple providers."""

import logging
import uuid
from difflib import SequenceMatcher

from bot.models.subtitle_result import SubtitleDownload, SubtitleResult, MAX_SUBTITLE_RESULTS
from bot.services.subtitle_providers.base import SubtitleProvider
from bot.services.subtitle_ranking_service import SubtitleRankingService

logger = logging.getLogger(__name__)


# In-memory mapping of file_id to SubtitleResult for download routing
_download_cache: dict[str, SubtitleResult] = {}

class SubtitleAggregatorService:
    """Aggregates and deduplicates subtitles from multiple providers."""

    def __init__(self, providers: list[SubtitleProvider]) -> None:
        self._providers = providers
        self._ranking_service = SubtitleRankingService()

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
        """Search all enabled providers and return merged, deduplicated, and ranked results."""
        all_results: list[SubtitleResult] = []

        for provider in self._providers:
            try:
                logger.info("Searching provider %s for query=%s", provider.name, query)
                results = provider.search_subtitles(
                    query=query,
                    tmdb_id=tmdb_id,
                    imdb_id=imdb_id,
                    media_type=media_type,
                    season=season,
                    episode=episode,
                    language=language,
                )
                all_results.extend(results)
            except Exception:
                logger.exception("Provider %s search failed", provider.name)

        if not all_results:
            return []

        deduplicated = self._deduplicate(all_results)
        ranked = self._ranking_service.rank(deduplicated, query)[:MAX_SUBTITLE_RESULTS]
        
        # Cache results for download and assign short file_ids
        for result in ranked:
            if not result.file_id or len(result.file_id) > 20:
                result.file_id = uuid.uuid4().hex[:12]
            _download_cache[result.file_id] = result
            
        return ranked

    def download_subtitle(self, file_id: str) -> SubtitleDownload:
        """Download subtitle using the cached provider information."""
        result = _download_cache.get(file_id)
        if not result:
            raise RuntimeError("Subtitle session expired or invalid.")

        for provider in self._providers:
            if provider.name == result.source:
                return provider.download_subtitle(result.provider_subtitle_id)

        raise RuntimeError(f"Unknown subtitle provider: {result.source}")

    def _deduplicate(self, results: list[SubtitleResult]) -> list[SubtitleResult]:
        """Deduplicate results by normalized file name or release name."""
        unique_results: list[SubtitleResult] = []
        seen_names = set()

        for result in results:
            name_to_check = (result.release_name or result.file_name).strip().lower()
            if not name_to_check:
                continue

            # Simple exact match deduplication
            if name_to_check in seen_names:
                continue
                
            # Fuzzy deduplication (avoid similar releases from different providers)
            is_duplicate = False
            for seen_name in seen_names:
                if SequenceMatcher(None, name_to_check, seen_name).ratio() > 0.95:
                    is_duplicate = True
                    break
                    
            if not is_duplicate:
                seen_names.add(name_to_check)
                unique_results.append(result)

        return unique_results
