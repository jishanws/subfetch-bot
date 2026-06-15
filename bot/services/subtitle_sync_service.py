"""Subtitle synchronization helpers."""

from pathlib import Path
import re


class SubtitleSyncError(RuntimeError):
    """Raised when subtitle synchronization fails."""


class UnsupportedSubtitleSyncError(SubtitleSyncError):
    """Raised when a subtitle format is not supported for sync."""


class SubtitleSyncService:
    """Shift SRT subtitle timing by a fixed number of seconds."""

    TIMESTAMP_PATTERN = re.compile(
        r"(?P<hours>\d{2}):(?P<minutes>\d{2}):(?P<seconds>\d{2}),(?P<millis>\d{3})"
    )

    def shift_srt_file(
        self,
        file_path: Path,
        original_file_name: str,
        shift_seconds: float,
    ) -> Path:
        """Create a shifted SRT file next to the retained original."""
        if file_path.suffix.lower() != ".srt":
            raise UnsupportedSubtitleSyncError("Only .srt files can be synchronized.")

        content = file_path.read_text(encoding="utf-8", errors="replace")
        shifted_content = self.shift_srt_content(content, shift_seconds)
        output_path = file_path.with_name(self.build_synced_file_name(original_file_name))
        output_path.write_text(shifted_content, encoding="utf-8")
        return output_path

    def shift_srt_content(self, content: str, shift_seconds: float) -> str:
        """Shift all SRT timestamps while preserving numbering and text."""
        shift_millis = int(round(shift_seconds * 1000))

        return self.TIMESTAMP_PATTERN.sub(
            lambda match: self._format_timestamp(
                max(self._timestamp_to_millis(match) + shift_millis, 0)
            ),
            content,
        )

    def build_synced_file_name(self, original_file_name: str) -> str:
        """Return the synced SRT file name for Telegram upload."""
        stem = Path(original_file_name).stem or "subtitle"
        return f"{stem}.synced.srt"

    def _timestamp_to_millis(self, match: re.Match[str]) -> int:
        hours = int(match.group("hours"))
        minutes = int(match.group("minutes"))
        seconds = int(match.group("seconds"))
        millis = int(match.group("millis"))
        return (((hours * 60) + minutes) * 60 + seconds) * 1000 + millis

    def _format_timestamp(self, millis: int) -> str:
        hours, remainder = divmod(millis, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        seconds, milliseconds = divmod(remainder, 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
