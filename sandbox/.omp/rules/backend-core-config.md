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

## Validation (Post-Hook)

`check-backend-core-config.ts` verifies settings validators, pool config, and
the error schema.

## Never Do These

- Skip `pool_size`/`max_overflow` when creating the engine
- Return raw `{"detail": ...}` from a new exception without `code`/`request_id`
- Accept an invalid `env` value silently
