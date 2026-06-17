"""In-memory short-term conversation state."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re


PENDING_EPISODE_TTL = timedelta(minutes=10)
PENDING_SYNC_TTL = timedelta(minutes=30)
pending_episode_requests: dict[int, "PendingEpisodeRequest"] = {}
pending_sync_requests: dict[int, "PendingSyncRequest"] = {}


@dataclass(frozen=True)
class PendingEpisodeRequest:
    """Pending TV episode clarification for a user."""

    user_id: int
    tmdb_id: int | None
    title: str
    media_type: str
    created_at: datetime
    original_query: str = ""
    normalized_title: str = ""
    year: int | None = None


@dataclass(frozen=True)
class PendingSyncRequest:
    """Pending subtitle sync request for a user."""

    file_path: Path
    original_file_name: str
    created_at: datetime
    direction: str | None = None


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
    EPISODE_SEASON_PATTERN = re.compile(
        r"\b(?:episode|ep)\s+0*(?P<episode>\d{1,3})\s+season\s+"
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

    def store_pending_sync_request(
        self,
        user_id: int,
        request: PendingSyncRequest,
    ) -> None:
        """Store a pending sync request for a Telegram user."""
        self.clear_pending_sync_request(user_id)
        pending_sync_requests[user_id] = request

    def get_pending_sync_request(
        self,
        user_id: int,
    ) -> PendingSyncRequest | None:
        """Return a pending sync request if one exists."""
        return pending_sync_requests.get(user_id)

    def set_pending_sync_direction(self, user_id: int, direction: str) -> None:
        """Store the known sync direction while waiting for an amount."""
        request = pending_sync_requests.get(user_id)
        if request is None:
            return
        pending_sync_requests[user_id] = PendingSyncRequest(
            file_path=request.file_path,
            original_file_name=request.original_file_name,
            created_at=request.created_at,
            direction=direction,
        )

    def is_pending_sync_expired(
        self,
        request: PendingSyncRequest,
        now: datetime | None = None,
    ) -> bool:
        """Return whether a pending sync request has expired."""
        current_time = now or datetime.now(timezone.utc)
        return current_time - request.created_at > PENDING_SYNC_TTL

    def clear_pending_sync_request(
        self,
        user_id: int,
        cleanup_file: bool = True,
    ) -> None:
        """Clear a user's pending sync request and optionally remove its files."""
        request = pending_sync_requests.pop(user_id, None)
        if request is None or not cleanup_file:
            return

        self._cleanup_sync_file(request.file_path)

    def parse_episode(self, message: str) -> tuple[int, int] | None:
        """Parse a season/episode pair from text."""
        for pattern in (
            self.COMPACT_EPISODE_PATTERN,
            self.SEASON_EPISODE_PATTERN,
            self.EPISODE_OF_SEASON_PATTERN,
            self.EPISODE_SEASON_PATTERN,
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
        title = request.normalized_title or request.title
        return f"{title} S{season:02d}E{episode:02d}"

    def _cleanup_sync_file(self, file_path: Path) -> None:
        """Remove a retained subtitle sync file if it exists."""
        try:
            file_path.unlink()
        except FileNotFoundError:
            return

        try:
            file_path.parent.rmdir()
        except OSError:
            return
