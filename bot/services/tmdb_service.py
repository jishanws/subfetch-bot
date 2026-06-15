"""TMDb search service."""

import logging
from typing import Any

import requests

from bot.models.search_result import MediaType, SearchResult

logger = logging.getLogger(__name__)


class TmdbServiceError(RuntimeError):
    """Base exception for TMDb service failures."""


class InvalidTmdbApiKeyError(TmdbServiceError):
    """Raised when TMDb rejects the configured API key."""


class TmdbNoResultsError(TmdbServiceError):
    """Raised when TMDb returns no usable movie or TV results."""


class TmdbNetworkError(TmdbServiceError):
    """Raised when TMDb cannot be reached."""


class TmdbService:
    """Client for TMDb movie and TV search endpoints."""

    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(
        self,
        api_key: str,
        session: requests.Session | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._session = session or requests.Session()
        self._timeout = timeout

    def search_movie(self, query: str) -> list[SearchResult]:
        """Search TMDb for movies matching the query."""
        logger.info("Searching TMDb movies for query=%s", query)
        payload = self._request("/search/movie", query)
        return self._parse_results(payload, media_type="movie")

    def search_tv(self, query: str) -> list[SearchResult]:
        """Search TMDb for TV shows matching the query."""
        logger.info("Searching TMDb TV shows for query=%s", query)
        payload = self._request("/search/tv", query)
        return self._parse_results(payload, media_type="tv")

    def multi_search(self, query: str) -> list[SearchResult]:
        """Search TMDb across movies and TV shows."""
        logger.info("Searching TMDb movies and TV shows for query=%s", query)
        payload = self._request("/search/multi", query)
        return self._parse_results(payload)

    def _request(self, endpoint: str, query: str) -> dict[str, Any]:
        """Execute a TMDb search request and return decoded JSON."""
        url = f"{self.BASE_URL}{endpoint}"
        params = {
            "api_key": self._api_key,
            "query": query,
            "include_adult": "false",
            "language": "en-US",
        }

        try:
            response = self._session.get(url, params=params, timeout=self._timeout)
        except requests.RequestException as exc:
            logger.exception("TMDb network request failed for endpoint=%s", endpoint)
            raise TmdbNetworkError("Could not reach TMDb. Please try again later.") from exc

        if response.status_code in {401, 403}:
            logger.error("TMDb rejected the configured API key.")
            raise InvalidTmdbApiKeyError("Invalid TMDb API key.")

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            logger.exception(
                "TMDb request failed with status=%s endpoint=%s",
                response.status_code,
                endpoint,
            )
            raise TmdbServiceError("TMDb request failed. Please try again later.") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            logger.exception("TMDb returned invalid JSON for endpoint=%s", endpoint)
            raise TmdbServiceError("TMDb returned an invalid response.") from exc

        if not isinstance(payload, dict):
            logger.error("TMDb returned unexpected payload type=%s", type(payload).__name__)
            raise TmdbServiceError("TMDb returned an invalid response.")

        return payload

    def _parse_results(
        self,
        payload: dict[str, Any],
        media_type: MediaType | None = None,
    ) -> list[SearchResult]:
        """Normalize TMDb API results into SearchResult objects."""
        raw_results = payload.get("results", [])
        if not isinstance(raw_results, list):
            logger.error("TMDb response did not include a valid results list.")
            raise TmdbServiceError("TMDb returned an invalid response.")

        results = [
            result
            for item in raw_results
            if (result := self._parse_result(item, media_type)) is not None
        ]

        if not results:
            logger.info("TMDb returned no usable results.")
            raise TmdbNoResultsError("No matching movies or TV shows found.")

        return results

    def _parse_result(
        self,
        item: Any,
        fallback_media_type: MediaType | None,
    ) -> SearchResult | None:
        """Parse a single TMDb result item."""
        if not isinstance(item, dict):
            return None

        media_type = item.get("media_type") or fallback_media_type
        if media_type not in {"movie", "tv"}:
            return None

        title = self._extract_title(item, media_type)
        tmdb_id = item.get("id")
        if not title or not isinstance(tmdb_id, int):
            return None

        return SearchResult(
            tmdb_id=tmdb_id,
            title=title,
            release_year=self._extract_release_year(item, media_type),
            media_type=media_type,
            overview=item.get("overview") or "",
            poster_path=item.get("poster_path"),
        )

    @staticmethod
    def _extract_title(item: dict[str, Any], media_type: str) -> str:
        if media_type == "movie":
            return str(item.get("title") or item.get("original_title") or "").strip()
        return str(item.get("name") or item.get("original_name") or "").strip()

    @staticmethod
    def _extract_release_year(item: dict[str, Any], media_type: str) -> int | None:
        date_key = "release_date" if media_type == "movie" else "first_air_date"
        date_value = item.get(date_key)

        if not isinstance(date_value, str) or len(date_value) < 4:
            return None

        year = date_value[:4]
        if not year.isdigit():
            return None

        return int(year)

