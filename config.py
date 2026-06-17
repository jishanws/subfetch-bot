"""Application configuration loaded from environment variables."""

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr, ValidationError


class Settings(BaseModel):
    """Validated application settings."""

    telegram_bot_token: SecretStr = Field(min_length=1)
    tmdb_api_key: SecretStr = Field(min_length=1)
    opensubtitles_api_key: SecretStr = Field(min_length=1)
    groq_api_key: SecretStr = Field(min_length=1)
    subdl_api_key: SecretStr | None = None
    proxy_url: SecretStr | None = None


class ConfigError(RuntimeError):
    """Raised when application configuration is invalid."""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and validate settings from the process environment and .env file."""
    load_dotenv()

    try:
        proxy_val = os.getenv("PROXY_URL", "").strip()
        subdl_val = os.getenv("SUBDL_API_KEY", "").strip()
        return Settings(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            tmdb_api_key=os.getenv("TMDB_API_KEY", ""),
            opensubtitles_api_key=os.getenv("OPENSUBTITLES_API_KEY", ""),
            groq_api_key=os.getenv("GROQ_API_KEY", ""),
            subdl_api_key=subdl_val if subdl_val else None,
            proxy_url=proxy_val if proxy_val else None,
        )
    except ValidationError as exc:
        field_names = {
            "telegram_bot_token": "TELEGRAM_BOT_TOKEN",
            "tmdb_api_key": "TMDB_API_KEY",
            "opensubtitles_api_key": "OPENSUBTITLES_API_KEY",
            "groq_api_key": "GROQ_API_KEY",
        }
        invalid_fields = [
            field_names[str(error["loc"][0])]
            for error in exc.errors()
            if error["loc"] and str(error["loc"][0]) in field_names
        ]
        invalid = ", ".join(invalid_fields)
        raise ConfigError(f"Missing required environment variables: {invalid}") from exc
