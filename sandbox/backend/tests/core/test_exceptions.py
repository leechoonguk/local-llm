"""Core exceptions tests — domain exception attributes + handler registration."""

from uuid import uuid4

import pytest
from fastapi import FastAPI
from sqlalchemy.orm.exc import StaleDataError
from starlette.testclient import TestClient

from app.core.exceptions import (
    AuthenticationError,
    BatchSkippedError,
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

    @app.get("/skipped")
    async def skipped() -> None:
        raise BatchSkippedError("ledger jobs are still walking: sync_food_ledger_recall")

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

        r = c.get("/skipped", headers=headers)
        # A job that stood down, answered to the operator who asked for it by
        # hand: the request was fine and the moment was not.
        assert r.status_code == 409
        assert r.json() == {
            "detail": "ledger jobs are still walking: sync_food_ledger_recall",
            "code": "batch_skipped",
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

    The bodies carry the provider's own answer where there was one, because the
    mapped sentence alone could not tell a refusal from a broken key. A timeout
    carries none: nothing answered, and an empty body would read as a provider
    that replied with nothing.
    """
    app = FastAPI()

    @app.get("/config")
    async def config() -> None:
        raise IntegrationConfigurationError("invalid")

    @app.get("/integration")
    async def integration() -> None:
        raise IntegrationError(
            "provider", "operation", "failed", status_code=200, body='{"CODE":"ERROR-334"}'
        )

    @app.get("/timeout")
    async def timeout() -> None:
        raise IntegrationTimeoutError("provider", "operation", "timeout")

    @app.get("/unreachable")
    async def unreachable() -> None:
        # A transport failure, the other case with nothing to show: the request
        # never reached a server, so there is no status and no body.
        raise IntegrationError("provider", "operation", "External API unreachable")

    @app.get("/limited")
    async def limited() -> None:
        raise IntegrationRateLimitError(
            "provider",
            "operation",
            "limited",
            retry_after=1.0,
            status_code=429,
            body="quota exceeded",
        )

    setup_exception_handler(app)
    with TestClient(app) as client:
        assert client.get("/config").status_code == 422
        refused = client.get("/integration")
        timed_out = client.get("/timeout")
        unreachable_response = client.get("/unreachable")
        response = client.get("/limited")
    assert refused.status_code == 502
    assert refused.json()["upstream"] == {"status_code": 200, "body": '{"CODE":"ERROR-334"}'}
    assert timed_out.status_code == 504
    assert "upstream" not in timed_out.json()
    assert unreachable_response.status_code == 502
    assert "upstream" not in unreachable_response.json()
    assert response.status_code == 429
    assert response.headers["retry-after"] == "1.0"
    assert response.json()["upstream"] == {"status_code": 429, "body": "quota exceeded"}


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
