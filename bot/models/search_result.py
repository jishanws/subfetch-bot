"""Search result models for resolved TMDb media."""

from typing import Literal

from pydantic import BaseModel, Field

MediaType = Literal["movie", "tv"]


class SearchResult(BaseModel):
    """Normalized movie or TV search result returned by TMDb."""

    tmdb_id: int = Field(gt=0)
    title: str = Field(min_length=1)
    release_year: int | None = None
    media_type: MediaType
    overview: str = ""
    poster_path: str | None = None

    @property
    def media_type_label(self) -> str:
        """Return a user-facing label for the media type."""
        if self.media_type == "tv":
            return "TV Show"
        return "Movie"

