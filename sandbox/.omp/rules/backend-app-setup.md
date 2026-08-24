---
description: Backend app setup — health check, OpenAPI metadata, API versioning
globs:
      - backend/app/main.py
      - backend/app/routers/health.py
alwaysApply: false
---

# Backend App Setup

## Purpose

Application-level setup in `main.py`: health endpoint, OpenAPI metadata, and
API versioning.

## 1. Health Check

`app/routers/health.py`:

```python
@router.get("/health")
async def health(session: SessionDep) -> dict:
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="DB unavailable")
    return {"status": "ok"}
```

- Returns 200 `{"status": "ok"}` when DB reachable, 503 otherwise
- Registered in `main.py` **outside** the `/api/v1` prefix (infra endpoint)

## 2. OpenAPI Metadata

```python
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="...",
)
```

- Tags from router `tags=[...]`; `/docs` reachable in dev only

## 3. API Versioning

- All domain routers mounted under `APIRouter(prefix="/api/v1")` in `main.py`
- Health stays at `/health` (no version)

## Validation (Post-Hook)

`check-backend-app-setup.ts` verifies health endpoint, OpenAPI metadata, and
the `/api/v1` prefix.

## Router Mounting

Every router module in `app/routers/` is mounted on `api_router`
(`APIRouter(prefix=API_V1_PREFIX)`) - except `health`, which is mounted directly
on `app` because probes use a fixed, unversioned path.

`check-backend-app-setup` compares the modules on disk against the mounts in
`main.py`: a router mounted on `app` is a second, unversioned API, and a router
that is never mounted answers nothing. Checking only that the string `/api/v1`
appears in `main.py` could see neither.

## Never Do These

- Add a router without mounting it under `/api/v1` (except health)
- Skip `title`/`version` in `FastAPI(...)`
