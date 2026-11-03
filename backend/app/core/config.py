from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Validated application settings loaded from the environment or project .env."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI Investment Research & Portfolio Copilot"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = (
        "postgresql+psycopg://copilot:copilot_dev_password@localhost:5432/"
        "investment_copilot"
    )
    database_echo: bool = False
    secret_key: str = "local-development-key-change-before-production"
    access_token_expire_minutes: int = 30

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.environment == "production" and (
            self.secret_key == "local-development-key-change-before-production"
            or len(self.secret_key) < 32
        ):
            raise ValueError("Production requires a SECRET_KEY of at least 32 characters.")
        if self.access_token_expire_minutes < 1:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be at least 1.")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
