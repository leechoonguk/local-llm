"""Shared fixtures: an isolated SQLite client, auth headers, and a hermetic env.

Every fixture here exists to keep a test from depending on something outside its
own file — the production engine, an ambient environment variable, or a token
minted by another test.
"""

from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.settings import Settings, settings
from app.main import app
from app.models.base import Base
from app.models.batch import Batch  # noqa: F401 — on metadata
from app.models.integration.call import IntegrationCall  # noqa: F401 — on metadata
from app.models.integration.field import IntegrationField  # noqa: F401 — on metadata
from app.models.integration.operation import IntegrationOperation  # noqa: F401 — on metadata
from app.models.integration.provider import Integration  # noqa: F401 — on metadata
from app.models.integration.secret import IntegrationSecret  # noqa: F401 — on metadata
from app.models.refresh import Refresh  # noqa: F401 — on metadata
from app.models.user import User  # noqa: F401 — on metadata


# Prevent scheduler from starting during tests
settings.env = "test"


@pytest.fixture(autouse=True)
def isolate_settings_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hide ambient environment variables that map to Settings fields.

    `Settings(_env_file=None, ...)` bypasses the .env file but **not**
    `os.environ`: pydantic-settings reads the process environment first. A shell
    (or CI job) that exported the root .env — `REDIS_URL`, `ITEMS_PER_USER`, … —
    therefore changed what the settings tests observed, and the same commit was
    green in one terminal and red in another.

    The names come from the model, not a hardcoded list, so a new field cannot
    reintroduce the leak.
    """
    for field in Settings.model_fields:
        monkeypatch.delenv(field.upper(), raising=False)
        monkeypatch.delenv(field, raising=False)


@pytest.fixture()
async def client() -> AsyncIterator[TestClient]:
    """Isolated in-memory SQLite client.

    The REAL get_session() dependency runs against a test engine swapped in
    place of the production one — the request lifecycle (session create /
    yield / close) is exercised, not a dependency override.
    """
    from app.dependencies import core as deps_core

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Point the session factory used by get_session() at the test engine.
    deps_core.async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    with TestClient(app) as c:
        yield c

    deps_core.async_session_factory = async_sessionmaker(  # reset for other fixtures
        engine, class_=AsyncSession, expire_on_commit=False
    )
    await engine.dispose()


@pytest.fixture()
def auth_headers(client: TestClient) -> dict[str, str]:
    """Create a test user and return Bearer auth headers."""
    client.post(
        "/api/v1/user/",
        json={"username": "tester", "email": "tester@example.com", "password": "secret-pass"},
    )
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "tester", "password": "secret-pass"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
async def engine():
    """In-memory SQLite engine with all tables — for repository/service tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture()
def factory(engine):
    """Session factory bound to the in-memory engine."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
