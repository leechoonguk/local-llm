---
description: Backend batch jobs — database-scheduled APScheduler jobs, cron rows, run/stop, and background task conventions
globs:
      - backend/app/batch/*
      - backend/app/core/scheduler.py
      - backend/app/main.py
alwaysApply: false
---

# Batch Jobs

## The schedule is a table, not a lifespan branch

`app/main.py` schedules nothing by name. The `batch` table is the job table:
one row per schedule, carrying `code` (which job), `cron` (when), and `enabled`
(whether the clock starts it). The lifespan reads every enabled row through
`BatchService.list_enabled_batches()` and hands each one to `BatchScheduler`.

That split is what makes the three operator verbs possible without a deploy:

| Want to… | Do | Reaches the scheduler via |
|---|---|---|
| change when a job runs | `PATCH /batch/{id}` with `cron` | `BatchScheduler.sync` |
| stop a job from being started by the clock | `PATCH /batch/{id}` with `enabled=false` | `BatchScheduler.sync` → `remove` |
| run one execution now | `POST /batch/{id}/run` `{"running": true}` | `BatchScheduler.run_now` |
| cancel the execution in flight | `POST /batch/{id}/run` `{"running": false}` | `BatchScheduler.stop` |

`enabled` is **activation**, not interruption: it decides whether the trigger
exists. `run`/`stop` act on one execution and never touch the trigger — a
deactivated row can still be run by hand, and a stopped run still fires on its
next cron. Collapsing the two would make "stop this run" silently unschedule a
nightly job.

- Scheduler is **disabled** when `settings.env == "test"`; `app.state.scheduler`
  is then `None` and `POST /{id}/run` answers 409 rather than accepting a run
  nothing would execute.
- A row whose `code` is not in `BATCH_JOBS` is skipped with a
  `batch_job_unknown` warning — one row from another deployment must not stop
  the others from scheduling.

## Job Registry (`app/core/scheduler.py`)

`BATCH_JOBS` is the only place a code becomes runnable Python:

```python
BATCH_JOBS: Mapping[str, BatchJob] = MappingProxyType(
    {
        "purge_expired_refreshes": purge_expired_refreshes,
    }
)
```

A code the registry does not carry is rejected at the API boundary
(`BatchCreateRequest._check_code` → 422), so an unrunnable schedule cannot be
stored. `validated_cron` proves the expression against the same `CronTrigger`
that will fire it, because a cron nobody can parse is a job that never runs.

## Batch Job Pattern (`app/batch/<name>.py`)

```python
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.core.exceptions import NotFoundError
from app.services.refresh import RefreshService


async def purge_expired_refreshes(days: int = 30) -> int:
    """Delete refresh tokens that expired more than the given number of days ago."""
    expired_before = datetime.now(UTC) - timedelta(days=days)

    # Read phase: a fresh session's close() releases the autobegun read
    # transaction. No session.begin() here — transactions belong to services.
    async with AsyncSession(engine) as session:
        refresh_service = RefreshService(session)
        expired = await refresh_service.find_expired(expired_before)
        expired_ids = [refresh.id for refresh in expired]

    # Write phase: each delete opens its own transaction via the service.
    deleted = 0
    async with AsyncSession(engine) as session:
        refresh_service = RefreshService(session)
        for refresh_id in expired_ids:
            try:
                await refresh_service.delete_refresh(refresh_id)
                deleted += 1
            except NotFoundError:
                continue

    return deleted
```

## Rules

1. **Use `engine` directly** from `app.core.database` — never receive session from DI
2. **Use `<domain>_service = Service(session)`** — services accept `AsyncSession`
   directly (batch jobs create their own session and pass it in); the local
   variable is domain-prefixed (`refresh_service`)
3. **Never access the repository** — repositories are private to their service.
   Call service methods instead: `refresh_service.find_expired(older_than)`,
   `refresh_service.delete_refresh(refresh_id)`. Raw session usage and
   `<domain>_service.<domain>_repository.*` are both forbidden
4. **Never call `session.begin()`** — transactions belong to the service layer
   (`backend-transaction.md`). Split read/write into separate sessions: the
   read session's `close()` releases the autobegun read transaction, and each
   write opens its own transaction inside the service method
5. **Return meaningful count/status** — batch jobs should report results
6. **No business logic** in batch jobs — use service layer methods
7. **A job takes no required arguments** — the registry calls it with none, so
   every parameter carries a default

## Adding a New Batch Job

1. Create `app/batch/<name>.py` following the pattern above — `make check-backend-batch`
   proves the shape (session-per-run, no HTTP-layer imports).
2. Register the callable in `BATCH_JOBS` (`app/core/scheduler.py`) **alongside**
   the existing entries — registries accumulate (rule://backend-domain).
3. Seed its `batch` row in a migration, one table per revision
   (`80_seed_purge_expired_refreshes_batch_job.py` is the model): a job that
   exists in Python but in no environment's database never runs.
4. Prove the run path with a targeted test (`make -C backend test-fast t="tests/batch/..."`)
   — the scheduler is disabled under `settings.env == "test"`, so the test calls the
   async function directly.
5. Finish with `make -C backend verify`; the root gate owns the final word.

## Job Registration

`BatchScheduler.sync` names every job's identity and its overlap policy:

| Option | Without it |
|---|---|
| `id=str(batch_id)` | the row's job cannot be replaced or stopped |
| `replace_existing=True` | a reload stacks a second copy of the job |
| `max_instances=1` | two runs act on the same rows at once |
| `coalesce=True` | a backlog fires once per missed interval |
| `misfire_grace_time=<s>` | a restart across the scheduled minute skips the run silently |

`sync` also removes before it adds: `replace_existing` only applies once the
scheduler is running, so before startup a second sync of one row would queue a
second pending job and the schedule would fire twice.

## Stopping an execution

`stop` cancels the asyncio task the executor is running — APScheduler can
unschedule a job but has no notion of interrupting a coroutine it already
handed to the loop. `_run` therefore registers `current_task()` under the row
id, re-raises `CancelledError` after logging `batch_job_stopped`, and clears
the entry in a `finally`. `stop` on a job that is not running returns `False`
instead of raising: the request states the wanted end state.

## Testing

- `settings.env = "test"` disables the scheduler
- Batch functions are `async def` — test with `pytest` + `asyncio`
- Never test against production database directly
- Use in-memory SQLite from `conftest.py` client fixture (see `backend-domain.md` Testing)
- Run/stop semantics need a **started** scheduler and a job that waits on an
  `asyncio.Event`; poll `is_running()` rather than sleeping a fixed time
  (`tests/core/test_scheduler.py`)

## Validation (Post-Hook)

`check-backend-batch.ts` enforces the whole chain, because every missing link
fails **silently** — each row below was reproduced by deleting the link and
watching the gate go red:

| Link | Checked | Without the check |
|---|---|---|
| `app/batch/<name>.py` defines `async def <job>` | every job function appears as a `BATCH_JOBS` value | an unregistered function is dead code nothing can schedule |
| `BATCH_JOBS` names a real function | every registry value is defined or imported | a code that resolves to nothing fails at 03:00, in the executor |
| a migration seeds the `batch` row | seeded codes are discovered from `op.bulk_insert` on `batch` — never a hardcoded list | a job that exists only in Python runs in no environment |
| `main.py` schedules nothing by name | `add_job(` is forbidden in `main.py` | a lifespan job cannot be rescheduled or stopped without a deploy |
| the lifespan reads the table | `main.py` calls `list_enabled_batches` | the process schedules whatever the last deploy hardcoded |
| `core/scheduler.py` `add_job` carries `id` / `replace_existing` / `max_instances` / `coalesce` / `misfire_grace_time` | option by option | duplicated, overlapping, or silently skipped runs |

**AST rules** (`.omp/ast-grep/rules/batch/`) add structural checks:

| Rule | Checks |
|---|---|
| `job-async.yml` | batch job functions must be `async def` |
| `service-constructor.yml` | must construct `<domain>_service = Service(session)` (positive rule — absence is a violation) |
| `session-from-engine.yml` | must create session via `async with AsyncSession(engine) as session:` (positive) |

Repository access is forbidden in batch jobs — enforced globally by
`naming/repository-access.yml` (batch is in its scan scope). Batch jobs call
service methods: `refresh_service.find_expired(...)`,
`refresh_service.delete_refresh(...)`.

String checks in the same hook cover: `engine` used directly, `service.repository`
access (never raw session), meaningful count/status return, and the `add_job`
option set wherever `main.py` schedules directly.
