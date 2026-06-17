"""SubDL subtitle provider."""

import io
import logging
import zipfile
from typing import Any

import requests

from bot.models.subtitle_result import SubtitleDownload, SubtitleResult
from bot.services.subtitle_providers.base import SubtitleProvider

logger = logging.getLogger(__name__)


class SubdlProvider(SubtitleProvider):
    """Subtitle provider for SubDL."""

    name = "subdl"
    BASE_URL = "https://api.subdl.com/api/v1/subtitles"
    DOWNLOAD_BASE_URL = "https://dl.subdl.com"

    def __init__(self, api_key: str, timeout: float = 10.0) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._session = requests.Session()

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
        """Search SubDL for subtitles."""
        if not self._api_key:
            return []

        logger.info("Searching SubDL for query=%s tmdb_id=%s", query, tmdb_id)
        params: dict[str, Any] = {
            "api_key": self._api_key,
            "languages": language.upper() if language else "EN"
        }

        if tmdb_id:
            params["tmdb_id"] = str(tmdb_id)
        elif imdb_id:
            params["imdb_id"] = str(imdb_id)
        else:
            params["film_name"] = query

        if media_type == "tv":
            params["type"] = "tv"
            if season is not None:
                params["season_number"] = str(season)
            if episode is not None:
                params["episode_number"] = str(episode)
        elif media_type == "movie":
            params["type"] = "movie"

        try:
            response = self._session.get(self.BASE_URL, params=params, timeout=self._timeout)
            response.raise_for_status()
            data = response.json()
        except Exception:
            logger.exception("SubDL API request failed")
            return []

        if not isinstance(data, dict) or not data.get("status"):
            return []

        subtitles_data = data.get("subtitles", [])
        if not isinstance(subtitles_data, list):
            return []

        results = []
        for sub in subtitles_data:
            if not isinstance(sub, dict):
                continue
                
            url = str(sub.get("url") or "").strip()
            if not url:
                continue

            file_name = str(sub.get("name") or sub.get("release_name") or "").strip()
            if not file_name.lower().endswith((".zip", ".srt", ".ass", ".sub")):
                file_name += ".zip"

            release_name = str(sub.get("release_name") or file_name).strip()
            sub_lang = str(sub.get("language") or language).strip()
            
            # Use url as provider_subtitle_id since we need it to download
            result = SubtitleResult(
                subtitle_id=url,
                file_id=url[:20], # This will be overridden by the aggregator
                language=sub_lang,
                file_name=file_name,
                download_count=0, # SubDL doesn't seem to provide download counts in this endpoint
                hearing_impaired=bool(sub.get("hi", False)),
                release_name=release_name,
                source=self.name,
                provider_subtitle_id=url,
                download_url=self.DOWNLOAD_BASE_URL + url
            )
            results.append(result)

        logger.info("SubDL returned %d results", len(results))
        return results

    def download_subtitle(self, subtitle_id: str) -> SubtitleDownload:
        """Download subtitle from SubDL. subtitle_id is the URL path from search results."""
        if not subtitle_id:
            raise RuntimeError("Missing SubDL download URL")

        full_url = self.DOWNLOAD_BASE_URL + subtitle_id
        
        try:
            response = self._session.get(full_url, timeout=self._timeout)
            response.raise_for_status()
        except Exception as exc:
            logger.exception("SubDL download failed")
            raise RuntimeError("SubDL download failed") from exc

        content = response.content
        file_name = subtitle_id.split("?")[0].split("/")[-1]

        # Extract if it's a zip file
        if file_name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as z:
                    # Find the first supported subtitle file
                    for name in z.namelist():
                        if name.lower().endswith((".srt", ".ass", ".sub")):
                            return SubtitleDownload(
                                file_name=name,
                                content=z.read(name)
                            )
            except Exception as exc:
                logger.exception("Failed to extract SubDL zip")
                raise RuntimeError("Failed to extract subtitle from zip") from exc

        return SubtitleDownload(file_name=file_name, content=content)
