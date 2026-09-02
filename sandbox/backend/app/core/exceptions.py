# ============================================================
# Imports
# ============================================================

from uuid import UUID

from fastapi import FastAPI, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from starlette.responses import JSONResponse


# ============================================================
# Constants
# ============================================================

REQUEST_ID_KEY = "request_id"

# The code a configuration failure carries when no narrower one fits. A cause a
# client must tell apart declares its own - `detail` is a log line, and the UI
# reads a translation keyed by the code.
CONFIGURATION_INVALID_CODE = "integration_configuration_invalid"


# ============================================================
# Classes
# ============================================================


class NotFoundError(Exception):
    """Raised when a resource is not found.

    Handled by setup_exception_handler — no need for HTTPException in routers.
    """

    def __init__(self, resource_id: UUID) -> None:
        super().__init__("Resource not found")
        self.resource_id = resource_id


class ConflictError(Exception):
    """Raised when a resource conflicts with existing data (e.g. unique
    constraint violation like a duplicate username/email).

    Handled by setup_exception_handler — no need for HTTPException in routers.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class IntegrationConfigurationError(Exception):
    """Raised when database-managed integration configuration is invalid.

    `code` is the contract: a taken provider code and a non-HTTPS base URL are
    different failures to a user filling a form, so they carry different codes
    and the client translates each one. `detail` stays English for the log.
    """

    def __init__(self, detail: str, code: str = CONFIGURATION_INVALID_CODE) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code


class IntegrationInputError(Exception):
    """Raised when a caller omits an input a request field declares required.

    Separate from IntegrationConfigurationError (the configuration is fine) and
    from IntegrationError (nothing upstream was called): the caller has to send
    the field. Maps to HTTP 422.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class AuthenticationError(Exception):
    """Raised when credentials are invalid (bad username or password).

    Handled by setup_exception_handler — no need for HTTPException in routers.
    """


class ServiceUnavailableError(Exception):
    """Raised when a dependency the app cannot serve without is unreachable.

    The readiness probe raises it so an orchestrator stops routing traffic; the
    handler answers 503 with the same body shape as every other failure.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class IntegrationError(Exception):
    """Raised when an external API call fails (network error, non-2xx after retries).

    Handled by setup_exception_handler — no need for HTTPException in routers.

    `status_code` and `body` carry the provider's own answer when there was one.
    Without them the API could only say "the call failed", and the one fact an
    operator needs to debug a provider — what the provider replied — was thrown
    away by our own error handler. A timeout and an unreachable host leave both
    None: there is no response to show.

    `envelope_key`/`envelope_value` carry the *reason* in the provider's own
    vocabulary when the refusal came from an envelope field: which declared
    field disagreed, and what it said. A caller that must tell one refusal from
    another — a paging job asking whether "no more data" is a failure or the end
    of the feed — otherwise has to parse `detail`, and a sentence is not an
    interface. Both are None when the call never reached an envelope check.
    """

    def __init__(
        self,
        provider: str,
        operation: str,
        detail: str,
        *,
        status_code: int | None = None,
        body: str | None = None,
        envelope_key: str | None = None,
        envelope_value: str | None = None,
    ) -> None:
        super().__init__(detail)
        self.provider = provider
        self.operation = operation
        self.detail = detail
        self.status_code = status_code
        self.body = body
        self.envelope_key = envelope_key
        self.envelope_value = envelope_value


class IntegrationTimeoutError(IntegrationError):
    """Raised when an external API call exceeds the configured timeout.

    Maps to HTTP 504 Gateway Timeout.
    """


class IntegrationRateLimitError(IntegrationError):
    """Raised when an external API responds 429 Too Many Requests.

    Maps to HTTP 429 with a Retry-After header when the provider supplies one.
    """

    def __init__(
        self,
        provider: str,
        operation: str,
        detail: str,
        retry_after: float | None = None,
        *,
        status_code: int | None = None,
        body: str | None = None,
    ) -> None:
        super().__init__(provider, operation, detail, status_code=status_code, body=body)
        self.retry_after = retry_after


# ============================================================
# Functions
# ============================================================


def _request_id(request: Request) -> str:
    return getattr(request.state, REQUEST_ID_KEY, request.headers.get("X-Request-ID", "unknown"))


def setup_exception_handler(app: FastAPI) -> None:
    """Register domain exception handlers to return uniform JSON responses."""

    @app.exception_handler(NotFoundError)
    async def _not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "detail": "Resource not found",
                "code": "not_found",
                REQUEST_ID_KEY: _request_id(request),
            },
        )

    @app.exception_handler(ConflictError)
    async def _conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "detail": exc.detail,
                "code": "conflict",
                REQUEST_ID_KEY: _request_id(request),
            },
        )

    @app.exception_handler(IntegrityError)
    async def _integrity_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        """A constraint the request violated: a duplicate key, a missing parent.

        Measured: re-sending an operation code answered 500 with a traceback, so
        the client could not tell a conflict from a broken server. The detail
        stays generic on purpose - a database message names columns and
        constraints the caller has no business reading.
        """
        return JSONResponse(
            status_code=409,
            content={
                "detail": "Request conflicts with existing data",
                "code": "conflict",
                REQUEST_ID_KEY: _request_id(request),
            },
        )

    @app.exception_handler(StaleDataError)
    async def _stale_data_handler(request: Request, exc: StaleDataError) -> JSONResponse:
        """Optimistic lock miss: another transaction updated the row first."""
        return JSONResponse(
            status_code=409,
            content={
                "detail": "Resource was modified by another request — reload and retry",
                "code": "stale_version",
                REQUEST_ID_KEY: _request_id(request),
            },
        )

    @app.exception_handler(IntegrationConfigurationError)
    async def _integration_configuration_handler(
        request: Request, exc: IntegrationConfigurationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": exc.detail,
                "code": exc.code,
                REQUEST_ID_KEY: _request_id(request),
            },
        )

    @app.exception_handler(IntegrationInputError)
    async def _integration_input_handler(
        request: Request, exc: IntegrationInputError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": exc.detail,
                "code": "integration_input_invalid",
                REQUEST_ID_KEY: _request_id(request),
            },
        )

    @app.exception_handler(AuthenticationError)
    async def _auth_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={
                "detail": "Incorrect username or password",
                "code": "authentication_failed",
                REQUEST_ID_KEY: _request_id(request),
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(ServiceUnavailableError)
    async def _service_unavailable_handler(
        request: Request, exc: ServiceUnavailableError
    ) -> JSONResponse:
        """Readiness failure: the dependency is down, the app is not serving."""
        return JSONResponse(
            status_code=503,
            content={
                "detail": exc.detail,
                "code": "service_unavailable",
                REQUEST_ID_KEY: _request_id(request),
            },
        )

    def _upstream(exc: IntegrationError) -> dict[str, object] | None:
        """The provider's own answer, when the provider gave one.

        Omitted rather than sent as null: a timeout has no response, and a key
        that is present but empty reads like a provider that answered nothing.
        It carries no request URL, no headers and no rendered path - every seeded
        provider carries its credential as a path segment, so echoing the request
        would publish the key through our own error.

        Only the shape is shared. Each handler keeps its own `detail`, `code` and
        request id literals, because `check-backend-exceptions` reads the body of
        the handler it governs and `check-frontend-i18n` discovers the server's
        error codes from those literals - a shared builder made both blind.
        """
        if exc.status_code is None:
            return None
        return {"status_code": exc.status_code, "body": exc.body}

    @app.exception_handler(IntegrationError)
    async def _integration_handler(request: Request, exc: IntegrationError) -> JSONResponse:
        content: dict[str, object] = {
            "detail": exc.detail,
            "code": "integration_error",
            "provider": exc.provider,
            "operation": exc.operation,
            REQUEST_ID_KEY: _request_id(request),
        }
        upstream = _upstream(exc)
        if upstream is not None:
            content["upstream"] = upstream
        return JSONResponse(status_code=502, content=content)

    @app.exception_handler(IntegrationTimeoutError)
    async def _integration_timeout_handler(
        request: Request, exc: IntegrationTimeoutError
    ) -> JSONResponse:
        # No `upstream` here, and not by omission: a timeout is the case where
        # nothing answered. The client never sets one on this class, so a branch
        # for it would be a line no request can reach.
        return JSONResponse(
            status_code=504,
            content={
                "detail": exc.detail,
                "code": "integration_timeout",
                "provider": exc.provider,
                "operation": exc.operation,
                REQUEST_ID_KEY: _request_id(request),
            },
        )

    @app.exception_handler(IntegrationRateLimitError)
    async def _integration_rate_limit_handler(
        request: Request, exc: IntegrationRateLimitError
    ) -> JSONResponse:
        headers = {}
        if exc.retry_after is not None:
            headers["Retry-After"] = str(exc.retry_after)
        content: dict[str, object] = {
            "detail": exc.detail,
            "code": "integration_rate_limited",
            "provider": exc.provider,
            "operation": exc.operation,
            REQUEST_ID_KEY: _request_id(request),
        }
        upstream = _upstream(exc)
        if upstream is not None:
            content["upstream"] = upstream
        return JSONResponse(status_code=429, content=content, headers=headers)
