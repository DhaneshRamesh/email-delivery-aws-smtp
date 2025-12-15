"""Application configuration powered by environment variables."""
from __future__ import annotations

from functools import lru_cache
from typing import List

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load variables from a local .env file if present. This keeps runtime flexible.
load_dotenv()


class Settings(BaseSettings):
    """Strongly typed configuration for the service."""

    app_name: str = "CourierX"
    environment: str = "development"
    api_version: str = "v1"
    database_url: str = "postgresql+psycopg://user:password@host:5432/database"
    redis_url: str = "redis://localhost:6379/0"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region_name: str = "us-east-1"
    ses_sender_email: str = "no-reply@example.com"
    allowed_origins: List[str] = ["http://localhost", "http://localhost:3000"]
    rate_limit_per_minute: int = 120

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    @field_validator("database_url", mode="before")
    @classmethod
    def strip_wrapping_quotes(cls, value: str) -> str:
        """Allow quoted URLs in env files."""
        if isinstance(value, str):
            return value.strip().strip('"').strip("'")
        return value

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, value: str | List[str]) -> List[str]:
        """Allow comma separated origins in env files."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("ses_sender_email")
    @classmethod
    def validate_sender(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError("ses_sender_email must contain '@'")
        return value


@lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings instance for reuse across the app."""

    return Settings()


settings = get_settings()
