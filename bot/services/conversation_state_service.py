"""In-memory short-term conversation state."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re


PENDING_EPISODE_TTL = timedelta(minutes=10)
pending_episode_requests: dict[int, "PendingEpisodeRequest"] = {}


@dataclass(frozen=True)
class PendingEpisodeRequest:
    """Pending TV episode clarification for a user."""

    tmdb_id: int | None
    title: str
    original_query: str
    normalized_title: str
    year: int | None
    created_at: datetime


class ConversationStateService:
    """Store and resolve short-lived per-user conversation state."""

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

    def store_pending_episode_request(
        self,
        user_id: int,
        request: PendingEpisodeRequest,
    ) -> None:
        """Store a pending episode request for a Telegram user."""
        pending_episode_requests[user_id] = request

    def get_pending_episode_request(
        self,
        user_id: int,
        now: datetime | None = None,
    ) -> PendingEpisodeRequest | None:
        """Return a pending episode request unless it has expired."""
        request = pending_episode_requests.get(user_id)
        if request is None:
            return None

        current_time = now or datetime.now(timezone.utc)
        if current_time - request.created_at > PENDING_EPISODE_TTL:
            self.clear_pending_episode_request(user_id)
            return None

        return request

    def clear_pending_episode_request(self, user_id: int) -> None:
        """Clear a user's pending episode request."""
        pending_episode_requests.pop(user_id, None)

    def parse_episode(self, message: str) -> tuple[int, int] | None:
        """Parse a season/episode pair from text."""
        for pattern in (
            self.COMPACT_EPISODE_PATTERN,
            self.SEASON_EPISODE_PATTERN,
            self.EPISODE_OF_SEASON_PATTERN,
        ):
            match = pattern.search(message)
            if match is not None:
                return int(match.group("season")), int(match.group("episode"))
        return None

    def build_episode_query(
        self,
        request: PendingEpisodeRequest,
        season: int,
        episode: int,
    ) -> str:
        """Combine a pending TV title with a parsed episode token."""
        return f"{request.normalized_title} S{season:02d}E{episode:02d}"
