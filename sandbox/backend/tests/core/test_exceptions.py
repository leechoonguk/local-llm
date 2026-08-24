"""Core exceptions tests — domain exception attributes + handler registration."""

from uuid import uuid4

import pytest
from fastapi import FastAPI
from sqlalchemy.orm.exc import StaleDataError
from starlette.testclient import TestClient

from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    IntegrationConfigurationError,
    IntegrationError,
    IntegrationRateLimitError,
    IntegrationTimeoutError,
    NotFoundError,
    setup_exception_handler,
)


def test_not_found_error_attributes() -> None:
    """The id stays on the exception while the message stays generic.

    Handlers need the id for logs; the client must not learn whether the row
    exists under a different owner.
    """
    resource_id = uuid4()
    exc = NotFoundError(resource_id)
    assert exc.resource_id == resource_id
    assert str(exc) == "Resource not found"


def test_conflict_error_attributes() -> None:
    """The detail passes through unchanged — the caller sees which value clashed."""
    exc = ConflictError("Username 'x' already exists")
    assert exc.detail == "Username 'x' already exists"
    assert str(exc) == "Username 'x' already exists"


def test_authentication_error_raises() -> None:
    """Constructible with no arguments: call sites must not invent a message."""
    with pytest.raises(AuthenticationError):
        raise AuthenticationError()


def test_setup_exception_handler_registers_handlers() -> None:
    """setup_exception_handler wires 404/409/401 JSON responses."""
    app = FastAPI()

    @app.get("/nf")
    async def nf() -> None:
        raise NotFoundError(uuid4())

    @app.get("/conflict")
    async def conflict() -> None:
        raise ConflictError("duplicate")

    @app.get("/auth")
    async def auth() -> None:
        raise AuthenticationError()

    setup_exception_handler(app)

    with TestClient(app) as c:
        headers = {"X-Request-ID": "test-request"}
        r = c.get("/nf", headers=headers)
        assert r.status_code == 404
        assert r.json() == {
            "detail": "Resource not found",
            "code": "not_found",
            "request_id": "test-request",
        }

        r = c.get("/conflict", headers=headers)
        assert r.status_code == 409
        assert r.json() == {
            "detail": "duplicate",
            "code": "conflict",
            "request_id": "test-request",
        }

        r = c.get("/auth", headers=headers)
        assert r.status_code == 401
        assert r.json() == {
            "detail": "Incorrect username or password",
            "code": "authentication_failed",
            "request_id": "test-request",
        }
        assert r.headers["www-authenticate"] == "Bearer"


def test_setup_exception_handler_registers_integration_handlers() -> None:
    """Each outbound failure maps to its own status, including Retry-After.

    Collapsing them to 500 would erase the difference between "provider is
    down", "provider was slow" and "back off for a second".
    """
    app = FastAPI()

    @app.get("/config")
    async def config() -> None:
        raise IntegrationConfigurationError("invalid")

    @app.get("/integration")
    async def integration() -> None:
        raise IntegrationError("provider", "operation", "failed")

    @app.get("/timeout")
    async def timeout() -> None:
        raise IntegrationTimeoutError("provider", "operation", "timeout")

    @app.get("/limited")
    async def limited() -> None:
        raise IntegrationRateLimitError("provider", "operation", "limited", retry_after=1.0)

    setup_exception_handler(app)
    with TestClient(app) as client:
        assert client.get("/config").status_code == 422
        assert client.get("/integration").status_code == 502
        assert client.get("/timeout").status_code == 504
        response = client.get("/limited")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "1.0"


def test_setup_exception_handler_maps_stale_version_to_409() -> None:
    """An optimistic lock miss surfaces as 409 with a stale_version code."""
    app = FastAPI()

    @app.get("/stale")
    async def stale() -> None:
        raise StaleDataError("UPDATE expected to update 1 row(s); 0 matched")

    setup_exception_handler(app)
    with TestClient(app) as client:
        response = client.get("/stale")

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "stale_version"
    assert "another request" in body["detail"]
