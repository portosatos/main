import pytest

from app.config import Settings

DB_URL = "postgresql+asyncpg://user:secret@db.example:5432/health"


@pytest.mark.xfail(strict=True, reason="step 0.2: not implemented")
def test_settings_load_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("DATABASE_URL", DB_URL)

    settings = Settings(_env_file=None)

    assert settings.app_env == "prod"
    assert settings.database_url == DB_URL


@pytest.mark.xfail(strict=True, reason="step 0.2: not implemented")
def test_app_env_defaults_to_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("DATABASE_URL", DB_URL)

    settings = Settings(_env_file=None)

    assert settings.app_env == "dev"
