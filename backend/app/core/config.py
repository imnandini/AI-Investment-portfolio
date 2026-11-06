from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    financial_data_provider: str = "none"
    financial_data_timeout_seconds: float = 5.0

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.environment == "production" and (
            self.secret_key == "local-development-key-change-before-production"
            or len(self.secret_key) < 32
        ):
            raise ValueError("Production requires a SECRET_KEY of at least 32 characters.")
        if self.access_token_expire_minutes < 1:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be at least 1.")
        if not self.financial_data_provider.strip():
            raise ValueError("FINANCIAL_DATA_PROVIDER cannot be blank.")
        if not 0 < self.financial_data_timeout_seconds <= 60:
            raise ValueError("FINANCIAL_DATA_TIMEOUT_SECONDS must be greater than 0 and at most 60.")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
