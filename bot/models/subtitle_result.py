"""Subtitle search result models."""

from pathlib import Path

from pydantic import BaseModel, Field

MAX_SUBTITLE_RESULTS = 12


class SubtitleResult(BaseModel):
    """Normalized subtitle metadata returned by OpenSubtitles or SubDL."""

    subtitle_id: str = Field(min_length=1)
    file_id: str = Field(min_length=1)
    language: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    download_count: int = Field(ge=0)
    hearing_impaired: bool = False
    release_name: str = ""
    source: str = "opensubtitles"
    provider_subtitle_id: str = ""
    download_url: str | None = None

    @property
    def language_label(self) -> str:
        """Return a user-facing language label."""
        language_names = {
            "en": "English",
            "eng": "English",
            "bn": "Bengali",
            "ben": "Bengali",
            "es": "Spanish",
            "spa": "Spanish",
            "fr": "French",
            "fre": "French",
            "de": "German",
            "ger": "German",
            "hi": "Hindi",
            "hin": "Hindi",
        }
        return language_names.get(self.language.lower(), self.language.title())


class SubtitleDownload(BaseModel):
    """Downloaded subtitle file content."""

    file_name: str = Field(min_length=1)
    content: bytes = Field(min_length=1)

    @property
    def extension(self) -> str:
        """Return the lowercase subtitle file extension."""
        return Path(self.file_name).suffix.lower()
