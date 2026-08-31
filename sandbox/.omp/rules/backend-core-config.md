---
description: Backend core config — settings validation, DB pool, error response schema
globs:
      - backend/app/core/settings.py
      - backend/app/core/database.py
      - backend/app/core/exceptions.py
alwaysApply: false
---

# Backend Core Config

## Purpose

Core configuration standards: Pydantic settings validation, explicit DB pool
config, and a uniform error response schema.

## 1. Settings Validation

```python
@field_validator("env")
@classmethod
def _validate_env(cls, v: str) -> str:
    if v not in {"local", "production", "test"}:
        raise ValueError("env must be local|production|test")
    return v
```

- `env` enum: `local` | `production` | `test`
- `DATABASE_URL` must start with `postgresql+asyncpg://` or `sqlite+aiosqlite://`

## 2. DB Pool Config

```python
engine = create_async_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_pre_ping=True,
)
```

- Explicit `pool_size`/`max_overflow`/`pool_timeout` — never rely on defaults

## 3. Error Response Schema

- `core/exceptions.py` handlers return `{"detail", "code", "request_id"}`
- `code` is a stable machine-readable string (e.g. `not_found`, `conflict`)
- `request_id` from the request middleware context
- An integration failure adds `provider`, `operation`, and — when the provider
  actually answered — `upstream: {"status_code", "body"}`. It is **absent**, not
  null, for a timeout or an unreachable host: there is no response to show, and an
  empty body reads like a provider that replied with nothing. Measured reason it
  exists: the screen could only print "외부 API 호출이 실패했습니다", so a provider
  refusal that arrives as HTTP 200 with `ERROR-334` in its wrapper was
  indistinguishable from a broken key — our own handler threw away the one fact
  that told them apart. `body` is capped (`UPSTREAM_BODY_LIMIT`) and every secret
  the call sent is replaced by `***` before it leaves the process; the payload
  carries no request URL, no headers and no rendered path, because these providers
  take the credential as a path segment and echo the request back.
- Each handler writes its own `detail`/`code`/`request_id` literals. Only the
  `upstream` shape is shared: `check-backend-exceptions` reads the body of the
  handler it governs, and `check-frontend-i18n` discovers the server's error codes
  from those literals, so a shared body builder made both checks blind.

## Validation (Post-Hook)

`check-backend-core-config.ts` verifies settings validators, pool config, and
the error schema.

## Never Do These

- Skip `pool_size`/`max_overflow` when creating the engine
- Return raw `{"detail": ...}` from a new exception without `code`/`request_id`
- Accept an invalid `env` value silently
