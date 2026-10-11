"""Application settings from environment variables (and an optional .env file)."""

from pathlib import Path
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
    # How long a process trusts its cached dev clock offset (ADR-025).
    clock_cache_ttl_s: float = 1.0
    # Demo user created by `python -m app.seed` on api start; an empty password skips it.
    demo_user_email: str = "demo@example.com"
    demo_user_password: str = ""
    demo_user_timezone: str = "Europe/Moscow"
    # Uploaded files (SPEC F3): a volume shared by the api and the worker.
    ingest_dir: Path = Path("/data/ingest")
    ingest_max_bytes: int = 500 * 1024 * 1024
    # /api/health calls the worker stale when its last tick is older than this.
    worker_stale_after_s: float = 120.0
    # SSE keep-alive: a comment line this often, in seconds, so proxies keep the stream open.
    sse_ping_s: int = 15
    # Digests (SPEC F10, ADR-050): SMTP of Mailpit, the link in the letter, the window and the cap
    # of the planner, the dispatcher's tick.
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_timeout_s: float = 10.0
    mail_from: str = "Трекер здоровья <noreply@health-tracker.local>"
    app_url: str = "http://localhost:5173"
    digest_window_minutes: int = 15
    digest_max_delay_minutes: int = 60
    digest_tick_s: float = 30.0
