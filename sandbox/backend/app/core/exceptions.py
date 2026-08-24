# ============================================================
# Imports
# ============================================================

from uuid import UUID

from fastapi import FastAPI, Request
from sqlalchemy.orm.exc import StaleDataError
from starlette.responses import JSONResponse


# ============================================================
# Constants
# ============================================================

REQUEST_ID_KEY = "request_id"


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
    """Raised when database-managed integration configuration is invalid."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


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
    """

    def __init__(self, provider: str, operation: str, detail: str) -> None:
        super().__init__(detail)
        self.provider = provider
        self.operation = operation
        self.detail = detail


class IntegrationTimeoutError(IntegrationError):
    """Raised when an external API call exceeds the configured timeout.

    Maps to HTTP 504 Gateway Timeout.
    """


class IntegrationRateLimitError(IntegrationError):
    """Raised when an external API responds 429 Too Many Requests.

    Maps to HTTP 429 with a Retry-After header when the provider supplies one.
    """

    def __init__(
        self, provider: str, operation: str, detail: str, retry_after: float | None = None
    ) -> None:
        super().__init__(provider, operation, detail)
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
                "code": "integration_configuration_invalid",
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

    @app.exception_handler(IntegrationError)
    async def _integration_handler(request: Request, exc: IntegrationError) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content={
                "detail": exc.detail,
                "code": "integration_error",
                "provider": exc.provider,
                "operation": exc.operation,
                REQUEST_ID_KEY: _request_id(request),
            },
        )

    @app.exception_handler(IntegrationTimeoutError)
    async def _integration_timeout_handler(
        request: Request, exc: IntegrationTimeoutError
    ) -> JSONResponse:
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
        return JSONResponse(
            status_code=429,
            content={
                "detail": exc.detail,
                "code": "integration_rate_limited",
                "provider": exc.provider,
                "operation": exc.operation,
                REQUEST_ID_KEY: _request_id(request),
            },
            headers=headers,
        )
