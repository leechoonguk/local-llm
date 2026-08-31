---
description: Backend batch jobs — APScheduler, scheduled cleanup, and background task conventions
globs:
      - backend/app/batch/*
      - backend/app/main.py
alwaysApply: false
---

# Batch Jobs

## APScheduler

- `batch/batches.py` runs `purge_stale_batches` daily at 03:00 (cron).
- Scheduler is **disabled** when `settings.env == "test"`.
- New batch jobs go in `app/batch/`.

## Batch Job Pattern

```python
from datetime import UTC, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import engine
from app.services.batch import BatchService

async def purge_stale_batches(days: int = 30) -> int:
    """Delete batches older than the given number of days.

    Uses BatchService.delete_batch to reuse existing deletion logic.
    Returns the number of deleted batches.
    """
    older_than = datetime.now(UTC) - timedelta(days=days)

    # Read phase: a fresh session's close() releases the autobegun read
    # transaction. No session.begin() here — transactions belong to services.
    async with AsyncSession(engine) as session:
        batch_service = BatchService(session)
        stale_batches = await batch_service.find_stale(older_than)
        stale_ids = [batch.id for batch in stale_batches]

    # Write phase: each delete_batch opens its own transaction via the service.
    deleted = 0
    async with AsyncSession(engine) as session:
        batch_service = BatchService(session)
        for batch_id in stale_ids:
            try:
                await batch_service.delete_batch(batch_id)
                deleted += 1
            except NotFoundError:
                continue

    return deleted
```

## Rules

1. **Use `engine` directly** from `app.core.database` — never receive session from DI
2. **Use `<domain>_service = Service(session)`** — services accept `AsyncSession`
   directly (batch jobs create their own session and pass it in); the local
   variable is domain-prefixed (`batch_service`)
3. **Never access the repository** — repositories are private to their service.
   Call service methods instead: `batch_service.find_stale(older_than)`,
   `batch_service.delete_batch(batch_id)`. Raw session usage and
   `<domain>_service.<domain>_repository.*` are both forbidden
4. **Never call `session.begin()`** — transactions belong to the service layer
   (`backend-transaction.md`). Split read/write into separate sessions: the
   read session's `close()` releases the autobegun read transaction, and each
   write opens its own transaction inside the service method
5. **Return meaningful count/status** — batch jobs should report results
6. **No business logic** in batch jobs — use service layer methods

## Adding a New Batch Job

1. Create `app/batch/<name>.py` following the pattern above
2. Register in `app/main.py` `lifespan` hook if it's a scheduled task
3. Test with `settings.env == "test"` — scheduler is disabled
4. Add manual test for the async function if needed


## Job Registration

Every `add_job` names its own identity and its overlap policy:

| Option | Without it |
|---|---|
| `id="<job>"` | the job cannot be replaced or inspected |
| `replace_existing=True` | a reload stacks a second copy of the job |
| `max_instances=1` | two runs act on the same rows at once |
| `coalesce=True` | a backlog fires once per missed interval |
| `misfire_grace_time=<s>` | a restart across the scheduled minute skips the run silently |

## Testing

- `settings.env = "test"` disables the scheduler
- Batch functions are `async def` — test with `pytest` + `asyncio`
- Never test against production database directly
- Use in-memory SQLite from `conftest.py` client fixture (see `backend-domain.md` Testing)

## Validation (Post-Hook)

The `check-backend-batch.ts` post-hook validates batch jobs after tool
execution. **AST rules** (`.omp/ast-grep/rules/batch/`) add structural checks:

| Rule | Checks |
|---|---|
| `job-async.yml` | batch job functions must be `async def` |
| `service-constructor.yml` | must construct `<domain>_service = Service(session)` (positive rule — absence is a violation) |
| `session-from-engine.yml` | must create session via `async with AsyncSession(engine) as session:` (positive) |

Repository access is forbidden in batch jobs — enforced globally by
`naming/repository-access.yml` (batch is in its scan scope). Batch jobs call
service methods: `batch_service.find_stale(...)`, `batch_service.delete_batch(...)`.

String checks in the same hook cover: `engine` used directly, `service.repository`
access (never raw session), meaningful count/status return.
