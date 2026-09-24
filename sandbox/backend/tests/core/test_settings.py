"""Core settings tests — Settings model defaults and env loading."""

import pytest
from pydantic import ValidationError

from app.core.settings import Settings


def _settings(**overrides) -> Settings:
    """Build Settings with required fields, bypassing the .env file."""
    base = {
        "app_name": "Test App",
        "admin_email": "a@example.com",
        "items_per_user": 10,
        "env": "test",
        "database_url": "sqlite+aiosqlite://",
        "secret_key": "k",
        "integration_timeout_seconds": 30.0,
        "integration_connect_timeout_seconds": 5.0,
        "integration_max_retries": 3,
        "integration_retry_base_seconds": 0.5,
        "integration_retry_max_seconds": 8.0,
        "allowed_hosts": ["testserver"],
        "scheduler_timezone": "Asia/Seoul",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[call-arg]


def test_settings_defaults() -> None:
    """Optional fields must not become required by accident.

    Every value here is one a deployment may omit, so a lost default breaks
    startup rather than a test.
    """
    s = _settings()
    assert s.access_token_expire_minutes == 30
    assert s.algorithm == "HS256"
    assert s.cors_origins == ["http://localhost:25173"]
    assert s.redis_url is None
    assert s.integration_timeout_seconds == 30.0
    assert s.integration_connect_timeout_seconds == 5.0
    assert s.integration_max_retries == 3
    assert s.integration_retry_base_seconds == 0.5
    assert s.integration_retry_max_seconds == 8.0


def test_settings_overrides() -> None:
    """A supplied value wins over the default — the field is really configurable."""
    s = _settings(
        access_token_expire_minutes=60,
        algorithm="HS512",
        redis_url="redis://localhost:26379/0",
        integration_timeout_seconds=60.0,
        integration_max_retries=5,
    )
    assert s.access_token_expire_minutes == 60
    assert s.algorithm == "HS512"
    assert s.redis_url == "redis://localhost:26379/0"
    assert s.integration_timeout_seconds == 60.0
    assert s.integration_max_retries == 5


def test_settings_requires_required_fields() -> None:
    """Missing credentials fail at import, not at the first request.

    A silent default here would run production against a placeholder.
    """
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]  # missing required fields, no .env fallback


def test_settings_ignores_extra() -> None:
    """An unrelated variable in the environment must not become an attribute."""
    s = _settings(**{"unknown_field": "ignored"})
    assert not hasattr(s, "unknown_field")


def test_settings_validates_environment() -> None:
    """An unknown env name is refused, since code branches on it.

    A typo would otherwise silently select the development path in production.
    """
    with pytest.raises(ValidationError, match="env must be"):
        _settings(env="staging")


def test_settings_rejects_an_empty_host_allowlist() -> None:
    """An empty allowlist accepts nothing, which reads as "misconfigured, not open".

    Refusing it at startup keeps the failure at deploy time instead of turning
    every request into a 400 nobody can explain.
    """
    with pytest.raises(ValidationError, match="at least one host"):
        _settings(allowed_hosts=[])


def test_settings_rejects_an_unknown_scheduler_timezone() -> None:
    """A misspelt zone must stop startup, not silently schedule somewhere else.

    Unresolved, every cron row would fall back to the container's clock — UTC —
    and a nightly job would run nine hours from where its author put it.
    """
    with pytest.raises(ValidationError, match="not a known IANA zone"):
        _settings(scheduler_timezone="Asia/Sowl")


def test_settings_validates_async_database_url() -> None:
    """A sync driver URL is refused at startup instead of blocking the loop."""
    with pytest.raises(ValidationError, match="async PostgreSQL or SQLite"):
        _settings(database_url="postgresql://user:pass@host/db")


def test_an_exported_variable_outranks_the_dotenv_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """The process environment wins over the declared file.

    The deployment injects every value as an environment variable and ships no
    file, and the file is the local fallback - so a value the environment
    states must never be shadowed by one on disk. This is pydantic-settings'
    own order; it was reversed once and the test suite then read a developer's
    `.env` over the environment it declares for itself.
    """
    env_file = tmp_path / ".env"
    env_file.write_text(
        "APP_NAME = from-file\n"
        "ADMIN_EMAIL = file@example.com\n"
        "ITEMS_PER_USER = 1\n"
        "ENV = local\n"
        "DATABASE_URL = postgresql+asyncpg://app:app@localhost:25432/file\n"
        "SECRET_KEY = file-secret\n"
        'ALLOWED_HOSTS = ["localhost"]\n'
        "INTEGRATION_TIMEOUT_SECONDS = 1.0\n"
        "INTEGRATION_CONNECT_TIMEOUT_SECONDS = 1.0\n"
        "INTEGRATION_MAX_RETRIES = 1\n"
        "INTEGRATION_RETRY_BASE_SECONDS = 1.0\n"
        "INTEGRATION_RETRY_MAX_SECONDS = 1.0\n"
        "SCHEDULER_TIMEZONE = Asia/Seoul\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://app:app@postgres:5432/exported")
    monkeypatch.setenv("APP_NAME", "from-environment")

    s = Settings(_env_file=str(env_file))  # type: ignore[call-arg]

    assert s.database_url.endswith("/exported")
    assert s.app_name == "from-environment"
    # Keys the environment does not state still come from the file.
    assert s.admin_email == "file@example.com"


def test_environment_still_supplies_keys_the_file_omits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """The container has no .env: every value must still arrive from the environment."""
    empty = tmp_path / "empty.env"
    empty.write_text("", encoding="utf-8")
    for key, value in {
        "APP_NAME": "container",
        "ADMIN_EMAIL": "ops@example.com",
        "ITEMS_PER_USER": "7",
        "ENV": "production",
        "DATABASE_URL": "postgresql+asyncpg://app:app@postgres:5432/app",
        "SECRET_KEY": "container-secret",
        "ALLOWED_HOSTS": '["api.example.com"]',
        "INTEGRATION_TIMEOUT_SECONDS": "2.0",
        "INTEGRATION_CONNECT_TIMEOUT_SECONDS": "2.0",
        "INTEGRATION_MAX_RETRIES": "2",
        "INTEGRATION_RETRY_BASE_SECONDS": "2.0",
        "INTEGRATION_RETRY_MAX_SECONDS": "2.0",
        "SCHEDULER_TIMEZONE": "Asia/Seoul",
    }.items():
        monkeypatch.setenv(key, value)

    s = Settings(_env_file=str(empty))  # type: ignore[call-arg]

    assert s.app_name == "container"
    assert s.allowed_hosts == ["api.example.com"]
