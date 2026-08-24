"""Readiness: the probe answers from the database, and 503 comes from the handler."""

import pytest
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

import app.routers.health as health_router
from app.core.exceptions import ServiceUnavailableError
from app.main import app


class _Connection:
    """A connection whose `execute` raises on demand, standing in for the engine."""

    def __init__(self, error: Exception | None = None) -> None:
        """Store the failure to raise, or None for a healthy connection."""
        self.error = error

    async def __aenter__(self) -> "_Connection":
        """Enter the async context the router uses."""
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        """Leave the context without suppressing anything."""
        return None

    async def execute(self, statement) -> None:
        """Raise the configured failure, or succeed silently."""
        if self.error is not None:
            raise self.error


class _Engine:
    """An engine that hands out one prepared connection."""

    def __init__(self, connection: _Connection) -> None:
        """Hold the connection every `connect()` returns."""
        self.connection = connection

    def connect(self) -> _Connection:
        """Hand out the prepared connection."""
        return self.connection


@pytest.mark.asyncio
async def test_health_returns_ok_when_database_is_available(monkeypatch) -> None:
    """A reachable database is the only thing that makes readiness true."""
    monkeypatch.setattr(health_router, "engine", _Engine(_Connection()))

    assert await health_router.health() == {"status": "ok"}


def test_health_endpoint_returns_request_and_security_headers(client, monkeypatch) -> None:
    """The probe response carries the request id back and the security headers.

    Support correlates incidents by `X-Request-ID`; a probe that drops it makes
    the first minute of every investigation guesswork.
    """
    monkeypatch.setattr(health_router, "engine", _Engine(_Connection()))

    response = client.get("/health", headers={"X-Request-ID": "smoke-request"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"] == "smoke-request"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


@pytest.mark.asyncio
async def test_health_raises_service_unavailable_when_database_is_down(monkeypatch) -> None:
    """The router raises the core exception and states no status code itself."""
    monkeypatch.setattr(health_router, "engine", _Engine(_Connection(SQLAlchemyError("down"))))

    with pytest.raises(ServiceUnavailableError) as error:
        await health_router.health()

    assert error.value.detail == "Database unavailable"


def test_health_endpoint_answers_503_through_the_handler(client, monkeypatch) -> None:
    """The status code comes from the handler layer, not the raise site."""
    monkeypatch.setattr(health_router, "engine", _Engine(_Connection(SQLAlchemyError("down"))))

    response = client.get("/health", headers={"X-Request-ID": "down-request"})

    assert response.status_code == 503
    body = response.json()
    assert body["detail"] == "Database unavailable"
    assert body["code"] == "service_unavailable"
    assert body["request_id"] == "down-request"


def test_cors_is_registered_as_outermost_middleware() -> None:
    """CORS must wrap everything, or a rejected request loses its CORS headers.

    A browser then reports an opaque network error instead of the real status.
    """
    assert app.user_middleware[0].cls is CORSMiddleware
