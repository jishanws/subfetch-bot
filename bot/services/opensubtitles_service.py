"""OpenSubtitles search service."""

import logging
from typing import Any

import requests

from bot.models.subtitle_result import SubtitleDownload, SubtitleResult

logger = logging.getLogger(__name__)


class OpenSubtitlesServiceError(RuntimeError):
    """Base exception for OpenSubtitles service failures."""


class OpenSubtitlesAuthenticationError(OpenSubtitlesServiceError):
    """Raised when OpenSubtitles authentication fails."""


class OpenSubtitlesNoResultsError(OpenSubtitlesServiceError):
    """Raised when no subtitles are found."""


class OpenSubtitlesDowntimeError(OpenSubtitlesServiceError):
    """Raised when OpenSubtitles is unavailable or unreachable."""


class InvalidSubtitleQueryError(OpenSubtitlesServiceError):
    """Raised when a subtitle query is empty or invalid."""


class OpenSubtitlesDownloadLinkExpiredError(OpenSubtitlesServiceError):
    """Raised when a temporary OpenSubtitles download link has expired."""


class OpenSubtitlesFileUnavailableError(OpenSubtitlesServiceError):
    """Raised when a subtitle file is unavailable or unsupported."""


class OpenSubtitlesRateLimitError(OpenSubtitlesServiceError):
    """Raised when OpenSubtitles rate-limits download requests."""


class OpenSubtitlesService:
    """Client for OpenSubtitles metadata search."""

    BASE_URL = "https://api.opensubtitles.com/api/v1"
    USER_AGENT = "subfetch-bot v0.1"
    SUPPORTED_EXTENSIONS = {".srt", ".ass", ".sub"}

    def __init__(
        self,
        api_key: str,
        session: requests.Session | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._session = session or requests.Session()
        self._timeout = timeout
        self._token: str | None = None

    def authenticate(
        self,
        username: str | None = None,
        password: str | None = None,
    ) -> str | None:
        """Authenticate with OpenSubtitles when account credentials are provided.

        Search requests are authenticated with the configured API key. OpenSubtitles
        also supports a login token for account-bound operations, so this method is
        available for future phases without making account credentials mandatory.
        """
        if not username or not password:
            logger.info("Using OpenSubtitles API key authentication.")
            return None

        logger.info("Authenticating with OpenSubtitles login endpoint.")
        payload = {"username": username, "password": password}

        try:
            response = self._session.post(
                f"{self.BASE_URL}/login",
                json=payload,
                headers=self._base_headers(),
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            logger.exception("OpenSubtitles authentication request failed.")
            raise OpenSubtitlesDowntimeError(
                "Could not reach OpenSubtitles. Please try again later."
            ) from exc

        if response.status_code in {401, 403}:
            logger.error("OpenSubtitles login authentication failed.")
            raise OpenSubtitlesAuthenticationError("OpenSubtitles authentication failed.")

        if response.status_code >= 500:
            logger.error("OpenSubtitles login endpoint unavailable.")
            raise OpenSubtitlesDowntimeError("OpenSubtitles is unavailable.")

        try:
            response.raise_for_status()
            data = response.json()
        except (requests.HTTPError, ValueError) as exc:
            logger.exception("OpenSubtitles login returned an invalid response.")
            raise OpenSubtitlesAuthenticationError("OpenSubtitles authentication failed.") from exc

        token = data.get("token") if isinstance(data, dict) else None
        if not isinstance(token, str) or not token:
            logger.error("OpenSubtitles login response did not include a token.")
            raise OpenSubtitlesAuthenticationError("OpenSubtitles authentication failed.")

        self._token = token
        return token

    def search_subtitles(
        self,
        query: str,
        language: str = "en",
    ) -> list[SubtitleResult]:
        """Search OpenSubtitles for subtitle metadata."""
        query = query.strip()
        language = language.strip().lower()

        if not query:
            raise InvalidSubtitleQueryError("Subtitle query cannot be empty.")
        if not language:
            raise InvalidSubtitleQueryError("Subtitle language cannot be empty.")

        logger.info(
            "Searching OpenSubtitles for query=%s language=%s",
            query,
            language,
        )
        payload = self._request(
            "/subtitles",
            params={
                "query": query,
                "languages": language,
            },
        )
        return self._parse_results(payload)

    def download_subtitle(self, subtitle_id: str) -> SubtitleDownload:
        """Retrieve a subtitle file from OpenSubtitles.

        OpenSubtitles download requests are made with the provider file id. The
        public method keeps the phase contract name, so callers pass the callback
        payload id received from search results.
        """
        subtitle_id = subtitle_id.strip()
        if not subtitle_id:
            raise InvalidSubtitleQueryError("Subtitle id cannot be empty.")

        logger.info("Requesting OpenSubtitles download link for subtitle_id=%s", subtitle_id)
        payload = self._post_json("/download", json_payload={"file_id": subtitle_id})
        link = payload.get("link")
        file_name = str(payload.get("file_name") or f"subtitle-{subtitle_id}.srt").strip()

        if not isinstance(link, str) or not link:
            logger.error("OpenSubtitles download response did not include a link.")
            raise OpenSubtitlesFileUnavailableError("Subtitle file is unavailable.")

        self._validate_supported_file(file_name)
        content = self._download_file(link)
        return SubtitleDownload(file_name=file_name, content=content)

    def _request(self, endpoint: str, params: dict[str, str]) -> dict[str, Any]:
        """Execute an OpenSubtitles request and return decoded JSON."""
        try:
            response = self._session.get(
                f"{self.BASE_URL}{endpoint}",
                params=params,
                headers=self._authenticated_headers(),
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            logger.exception("OpenSubtitles request failed for endpoint=%s", endpoint)
            raise OpenSubtitlesDowntimeError(
                "Could not reach OpenSubtitles. Please try again later."
            ) from exc

        if response.status_code in {401, 403}:
            logger.error("OpenSubtitles rejected the configured credentials.")
            raise OpenSubtitlesAuthenticationError("OpenSubtitles authentication failed.")

        if response.status_code == 404:
            logger.info("OpenSubtitles returned no results.")
            raise OpenSubtitlesNoResultsError("No subtitles found.")

        if response.status_code >= 500:
            logger.error("OpenSubtitles API unavailable with status=%s", response.status_code)
            raise OpenSubtitlesDowntimeError("OpenSubtitles is unavailable.")

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            logger.exception(
                "OpenSubtitles request failed with status=%s endpoint=%s",
                response.status_code,
                endpoint,
            )
            raise OpenSubtitlesServiceError(
                "OpenSubtitles request failed. Please try again later."
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            logger.exception("OpenSubtitles returned invalid JSON.")
            raise OpenSubtitlesServiceError("OpenSubtitles returned an invalid response.") from exc

        if not isinstance(payload, dict):
            logger.error("OpenSubtitles returned unexpected payload type=%s", type(payload).__name__)
            raise OpenSubtitlesServiceError("OpenSubtitles returned an invalid response.")

        return payload

    def _post_json(self, endpoint: str, json_payload: dict[str, str]) -> dict[str, Any]:
        """Execute an OpenSubtitles JSON POST request."""
        try:
            response = self._session.post(
                f"{self.BASE_URL}{endpoint}",
                json=json_payload,
                headers=self._authenticated_headers(),
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            logger.exception("OpenSubtitles POST request failed for endpoint=%s", endpoint)
            raise OpenSubtitlesDowntimeError(
                "Could not reach OpenSubtitles. Please try again later."
            ) from exc

        if response.status_code in {401, 403}:
            logger.error("OpenSubtitles rejected download credentials.")
            raise OpenSubtitlesAuthenticationError("OpenSubtitles authentication failed.")

        if response.status_code == 404:
            logger.info("OpenSubtitles subtitle file was not found.")
            raise OpenSubtitlesFileUnavailableError("Subtitle file is unavailable.")

        if response.status_code == 429:
            logger.warning("OpenSubtitles rate-limited a download request.")
            raise OpenSubtitlesRateLimitError("Too many download requests.")

        if response.status_code >= 500:
            logger.error("OpenSubtitles download API unavailable with status=%s", response.status_code)
            raise OpenSubtitlesDowntimeError("OpenSubtitles is unavailable.")

        try:
            response.raise_for_status()
            payload = response.json()
        except requests.HTTPError as exc:
            logger.exception(
                "OpenSubtitles POST failed with status=%s endpoint=%s",
                response.status_code,
                endpoint,
            )
            raise OpenSubtitlesServiceError(
                "OpenSubtitles request failed. Please try again later."
            ) from exc
        except ValueError as exc:
            logger.exception("OpenSubtitles POST returned invalid JSON.")
            raise OpenSubtitlesServiceError("OpenSubtitles returned an invalid response.") from exc

        if not isinstance(payload, dict):
            logger.error("OpenSubtitles POST returned unexpected payload type=%s", type(payload).__name__)
            raise OpenSubtitlesServiceError("OpenSubtitles returned an invalid response.")

        return payload

    def _download_file(self, link: str) -> bytes:
        """Download subtitle bytes from a temporary OpenSubtitles file link."""
        try:
            response = self._session.get(link, timeout=self._timeout)
        except requests.RequestException as exc:
            logger.exception("OpenSubtitles temporary file download failed.")
            raise OpenSubtitlesDowntimeError(
                "Could not download subtitle file. Please try again later."
            ) from exc

        if response.status_code in {401, 403, 410}:
            logger.info("OpenSubtitles temporary download link expired.")
            raise OpenSubtitlesDownloadLinkExpiredError("Subtitle download link expired.")

        if response.status_code == 404:
            logger.info("OpenSubtitles temporary file was unavailable.")
            raise OpenSubtitlesFileUnavailableError("Subtitle file is unavailable.")

        if response.status_code >= 500:
            logger.error("OpenSubtitles file host unavailable with status=%s", response.status_code)
            raise OpenSubtitlesDowntimeError("OpenSubtitles file host is unavailable.")

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            logger.exception("OpenSubtitles file download failed with status=%s", response.status_code)
            raise OpenSubtitlesServiceError("Subtitle download failed.") from exc

        if not response.content:
            logger.error("OpenSubtitles returned an empty subtitle file.")
            raise OpenSubtitlesFileUnavailableError("Subtitle file is empty.")

        return response.content

    def _authenticated_headers(self) -> dict[str, str]:
        headers = self._base_headers()
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _base_headers(self) -> dict[str, str]:
        return {
            "Api-Key": self._api_key,
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _parse_results(self, payload: dict[str, Any]) -> list[SubtitleResult]:
        raw_results = payload.get("data", [])
        if not isinstance(raw_results, list):
            logger.error("OpenSubtitles response did not include a valid data list.")
            raise OpenSubtitlesServiceError("OpenSubtitles returned an invalid response.")

        results = [
            result
            for item in raw_results
            if (result := self._parse_result(item)) is not None
        ]

        if not results:
            logger.info("OpenSubtitles returned no usable subtitle results.")
            raise OpenSubtitlesNoResultsError("No subtitles found.")

        return results

    def _parse_result(self, item: Any) -> SubtitleResult | None:
        if not isinstance(item, dict):
            return None

        attributes = item.get("attributes", {})
        if not isinstance(attributes, dict):
            return None

        subtitle_id = str(attributes.get("subtitle_id") or item.get("id") or "").strip()
        file_id = self._extract_file_id(attributes)
        language = str(attributes.get("language") or "").strip()
        file_name = self._extract_file_name(attributes)
        release_name = str(attributes.get("release") or "").strip()

        if not subtitle_id or not file_id or not language or not file_name:
            return None

        return SubtitleResult(
            subtitle_id=subtitle_id,
            file_id=file_id,
            language=language,
            file_name=file_name,
            download_count=self._to_int(attributes.get("download_count")),
            hearing_impaired=bool(attributes.get("hearing_impaired", False)),
            release_name=release_name or file_name,
        )

    @staticmethod
    def _extract_file_id(attributes: dict[str, Any]) -> str:
        files = attributes.get("files", [])
        if isinstance(files, list):
            for file_item in files:
                if not isinstance(file_item, dict):
                    continue
                file_id = str(file_item.get("file_id") or "").strip()
                if file_id:
                    return file_id

        return str(attributes.get("file_id") or "").strip()

    @staticmethod
    def _extract_file_name(attributes: dict[str, Any]) -> str:
        files = attributes.get("files", [])
        if isinstance(files, list):
            for file_item in files:
                if not isinstance(file_item, dict):
                    continue
                file_name = str(file_item.get("file_name") or "").strip()
                if file_name:
                    return file_name

        return str(attributes.get("file_name") or "").strip()

    @staticmethod
    def _to_int(value: Any) -> int:
        if isinstance(value, int):
            return max(value, 0)
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return 0

    def _validate_supported_file(self, file_name: str) -> None:
        extension = f".{file_name.rsplit('.', maxsplit=1)[-1].lower()}" if "." in file_name else ""
        if extension not in self.SUPPORTED_EXTENSIONS:
            logger.error("Unsupported subtitle extension=%s file_name=%s", extension, file_name)
            raise OpenSubtitlesFileUnavailableError("Unsupported subtitle file type.")
