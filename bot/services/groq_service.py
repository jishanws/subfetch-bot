"""Small Groq fallback client for title correction."""

import json
import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


class GroqServiceError(RuntimeError):
    """Raised when Groq title correction fails."""


class GroqService:
    """Client for minimal Groq title correction requests."""

    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
    MODEL = "llama-3.1-8b-instant"

    def __init__(
        self,
        api_key: str,
        session: requests.Session | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._session = session or requests.Session()
        self._timeout = timeout

    def correct_title(self, query: str) -> str | None:
        """Return a corrected movie/TV query, or None when unavailable."""
        query = query.strip()
        if not query:
            return None

        payload = {
            "model": self.MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Correct movie/TV title only. Return JSON.\n"
                        'Example Input: "the shawshank redemtion"\n'
                        'Example Output: {"query":"the shawshank redemption"}\n'
                        f'Input: "{query}"'
                    ),
                }
            ],
            "temperature": 0,
            "max_tokens": 50,
        }

        try:
            response = self._session.post(
                self.BASE_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.exception("Groq title correction request failed.")
            raise GroqServiceError("Groq title correction failed.") from exc

        content = self._extract_content(data)
        return self._parse_corrected_query(content)

    def classify_sync_message(self, message: str) -> str:
        """Classify a subtitle sync message as perfect, early, late, or unknown."""
        message = message.strip()
        if not message:
            return "unknown"

        payload = {
            "model": self.MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Classify subtitle sync message. Return JSON only.\n"
                        "Options: perfect, early, late, unknown.\n"
                        f'Text: "{message}"'
                    ),
                }
            ],
            "temperature": 0,
            "max_tokens": 30,
        }

        try:
            response = self._session.post(
                self.BASE_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.exception("Groq sync intent request failed.")
            raise GroqServiceError("Groq sync intent classification failed.") from exc

        content = self._extract_content(data)
        return self._parse_sync_intent(content)

    def _extract_content(self, data: Any) -> str:
        if not isinstance(data, dict):
            raise GroqServiceError("Groq returned an invalid response.")

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise GroqServiceError("Groq returned no choices.")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise GroqServiceError("Groq returned an invalid choice.")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise GroqServiceError("Groq returned an invalid message.")

        content = message.get("content")
        if not isinstance(content, str):
            raise GroqServiceError("Groq returned invalid content.")

        return content.strip()

    def _parse_corrected_query(self, content: str) -> str | None:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            start = content.find("{")
            end = content.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise GroqServiceError("Groq did not return JSON.") from exc
            parsed = json.loads(content[start : end + 1])

        if not isinstance(parsed, dict):
            raise GroqServiceError("Groq JSON was not an object.")

        corrected = parsed.get("query")
        if not isinstance(corrected, str):
            raise GroqServiceError("Groq JSON did not include query.")

        corrected = corrected.strip()
        return corrected or None

    def _parse_sync_intent(self, content: str) -> str:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            start = content.find("{")
            end = content.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise GroqServiceError("Groq did not return JSON.") from exc
            parsed = json.loads(content[start : end + 1])

        if not isinstance(parsed, dict):
            raise GroqServiceError("Groq JSON was not an object.")

        intent = parsed.get("intent") or parsed.get("sync")
        if not isinstance(intent, str):
            raise GroqServiceError("Groq JSON did not include intent.")

        intent = intent.strip().lower()
        if intent not in {"perfect", "early", "late", "unknown"}:
            return "unknown"
        return intent
