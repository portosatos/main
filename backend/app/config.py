"""Application settings from environment variables (and an optional .env file)."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["dev", "test", "prod"]


class Settings(BaseSettings):
    # .env is looked up in the working directory and its parent (repo root when run from backend/).
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_env: AppEnv = "dev"
    database_url: str
    # Upper bound for the DB check in /api/health, so a dead DB does not hang healthchecks.
    db_health_timeout_s: float = 2.0
