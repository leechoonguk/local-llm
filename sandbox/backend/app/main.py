# ============================================================
# Imports
# ============================================================

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

import httpx2
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.batch.batches import purge_stale_batches
from app.core.cache import RedisCache
from app.core.exceptions import setup_exception_handler
from app.core.logging import configure_logging
from app.core.settings import settings
from app.routers import auth, batch, health, integration, notice, user


# ============================================================
# Constants
# ============================================================

API_V1_PREFIX = "/api/v1"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

configure_logging(settings.env)
logger = structlog.get_logger(__name__)


# ============================================================
# Middleware
# ============================================================

class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response


class CsrfProtection(BaseHTTPMiddleware):
    """Reject unsafe browser requests from untrusted origins.

    Bearer credentials are not sent automatically by browsers, so this API
    does not issue a CSRF token. Origin validation and Fetch Metadata protect
    state-changing endpoints without breaking non-browser Bearer clients.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.trusted_origins = frozenset(
            origin.rstrip("/") for origin in settings.cors_origins if origin != "*"
        )

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method in SAFE_METHODS:
            return await call_next(request)

        origin = request.headers.get("Origin")
        trusted_origin = origin is not None and origin.rstrip("/") in self.trusted_origins
        fetch_site = request.headers.get("Sec-Fetch-Site")
        if (origin is not None and not trusted_origin) or (
            fetch_site == "cross-site" and not trusted_origin
        ):
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF validation failed"},
                headers={"Vary": "Origin, Sec-Fetch-Site"},
            )

        response = await call_next(request)
        response.headers["Vary"] = "Origin, Sec-Fetch-Site"
        return response


# ============================================================
# Lifespan
# ============================================================

@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None]:
    scheduler: AsyncIOScheduler | None = None
    redis_client: Redis | None = None
    integration_http_client = httpx2.AsyncClient(
        timeout=httpx2.Timeout(
            settings.integration_timeout_seconds,
            connect=settings.integration_connect_timeout_seconds,
        ),
        # An unbounded pool turns one slow provider into every worker waiting on
        # a socket. The ceiling is what keeps a provider outage local.
        limits=httpx2.Limits(max_connections=100, max_keepalive_connections=20),
    )
    app.state.integration_http_client = integration_http_client
    if settings.redis_url is not None and settings.env != "test":
        try:
            redis_client = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                # A pooled connection that died during a failover is otherwise
                # handed to a request and fails it once per connection.
                health_check_interval=30,
            )
            await redis_client.ping()
            app.state.redis_cache = RedisCache(redis_client)
            logger.info("redis_cache_connected")
        except RedisError:
            logger.warning("redis_cache_unavailable")
            if redis_client is not None:
                await redis_client.aclose()
            app.state.redis_cache = None
    else:
        app.state.redis_cache = None

    if settings.env != "test":
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            purge_stale_batches,
            "cron",
            hour=3,
            minute=0,
            kwargs={"days": 30},
            # A named job replaces itself instead of stacking a second copy on
            # every reload; one instance at a time, because two purges racing
            # delete the same rows twice. A restart across 03:00 still runs the
            # job (coalesced into one) as long as it is less than an hour late.
            id="purge_stale_batches",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
        )
        scheduler.start()
        app.state.scheduler = scheduler

    yield
    await integration_http_client.aclose()
    if scheduler is not None:
        scheduler.shutdown(wait=False)
    if redis_client is not None:
        await redis_client.aclose()


# ============================================================
# App Setup
# ============================================================

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Fast API Standard backend",
    lifespan=_lifespan,
)
setup_exception_handler(app)
# Host header first: a request for an unknown host is refused before any other
# middleware spends work on it, and before a generated URL can be poisoned.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(CsrfProtection)
app.add_middleware(SecurityHeaders)


@app.middleware("http")
async def request_context(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    started = perf_counter()
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        logger.exception("request_failed", status_code=500)
        raise
    finally:
        logger.info(
            "request_completed",
            status_code=status_code,
            duration_ms=round((perf_counter() - started) * 1000, 2),
        )
        structlog.contextvars.clear_contextvars()
    response.headers["X-Request-ID"] = request_id
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Router Registration
# ============================================================

app.include_router(health.router)

api_router = APIRouter(prefix=API_V1_PREFIX)
api_router.include_router(batch.router)
api_router.include_router(integration.router)
api_router.include_router(notice.router)
api_router.include_router(user.router)
api_router.include_router(auth.router)
app.include_router(api_router)
