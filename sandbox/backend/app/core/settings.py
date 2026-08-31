# ============================================================
# Imports
# ============================================================

from pydantic import field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


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

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Let `.env` outrank an exported variable.

        pydantic-settings defaults to environment variables winning over the
        dotenv file, so a shell that exported docker-compose's values silently
        redirected every local run at hosts that resolve only inside compose
        (measured: alembic and uvicorn died with "nodename nor servname
        provided"). `.env` is the declared source for a local run
        (environment.md), so it wins here and no caller has to strip anything.

        The container is unaffected: the image copies no `.env`
        (backend/Dockerfile), so this source is empty there and docker-compose's
        environment stays the only input.
        """
        return (init_settings, dotenv_settings, env_settings, file_secret_settings)

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

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        allowed = ("postgresql+asyncpg://", "sqlite+aiosqlite://")
        if not value.startswith(allowed):
            raise ValueError("database_url must use an async PostgreSQL or SQLite scheme")
        return value


settings = Settings()  # type: ignore[call-arg]
