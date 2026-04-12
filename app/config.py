from enum import Enum
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class AIProvider(str, Enum):
    TEST = "test"
    ANTHROPIC = "anthropic"


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or a .env file."""

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/meal_planner"

    secret_key: str = "<SECRET_KEY>"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 1 day

    ai_provider: AIProvider = AIProvider.ANTHROPIC

    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "<ANTHROPIC_MODEL>"

    environment: str = "development"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


