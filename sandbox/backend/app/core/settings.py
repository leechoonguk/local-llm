# ============================================================
# Imports
# ============================================================

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ============================================================
# Classes
# ============================================================


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str
    admin_email: str
    items_per_user: int
    env: str
    database_url: str
    redis_url: str | None = None
    secret_key: str
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    # Secure-by-default: the refresh cookie is only ever sent over https unless a
    # deployment explicitly opts out (local http dev) — security code must not
    # branch on `env` (environment.md), the decision gets its own switch.
    cookie_secure: bool = True
    algorithm: str = "HS256"
    cors_origins: list[str] = ["http://localhost:25173"]
    # Required, not defaulted: a Host allowlist that falls back to "accept
    # anything" is the vulnerability it exists to close, and a missing value
    # must stop startup instead of opening the app.
    allowed_hosts: list[str]
    # External API integration transport (see backend-integration.md).
    integration_timeout_seconds: float
    integration_connect_timeout_seconds: float
    integration_max_retries: int
    integration_retry_base_seconds: float
    integration_retry_max_seconds: float
    # The wall clock every `batch_schedule.cron` is read against. Required, not
    # defaulted: without it APScheduler reads a cron in the container's zone,
    # which is UTC, and a row an operator wrote as 04:00 fires at 13:00 Seoul
    # time with nothing anywhere saying so. Day anchors are where that turns
    # into a wrong day - "the 1st at 04:00" written as UTC is the 31st.
    scheduler_timezone: str

    # Source order is pydantic-settings' own: an environment variable outranks
    # `.env`. That is the deployment contract - every container gets its values
    # injected by compose and carries no file (backend/.dockerignore) - and the
    # file is the local fallback for a process started by hand. It was reversed
    # once, so that a shell which had exported compose's values could not point
    # a local run at hosts only compose resolves; that run died loudly
    # ("nodename nor servname provided"), which is the right outcome for a
    # polluted shell, whereas the reversal made the test suite read the
    # developer's `.env` over the environment the suite declares for itself
    # and pass locally on values CI never saw.

    @field_validator("env")
    @classmethod
    def validate_env(cls, value: str) -> str:
        if value not in {"local", "production", "test"}:
            raise ValueError("env must be local|production|test")
        return value

    @field_validator("allowed_hosts")
    @classmethod
    def validate_allowed_hosts(cls, value: list[str]) -> list[str]:
        if len(value) == 0:
            raise ValueError("allowed_hosts must name at least one host")
        return value

    @field_validator("scheduler_timezone")
    @classmethod
    def validate_scheduler_timezone(cls, value: str) -> str:
        # Resolved here so a typo stops startup rather than every cron row
        # silently falling back to the container's zone at the first fire.
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"scheduler_timezone is not a known IANA zone: {value}") from exc
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        allowed = ("postgresql+asyncpg://", "sqlite+aiosqlite://")
        if not value.startswith(allowed):
            raise ValueError("database_url must use an async PostgreSQL or SQLite scheme")
        return value


settings = Settings()  # type: ignore[call-arg]
