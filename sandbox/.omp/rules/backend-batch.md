---
description: Backend batch jobs — database-scheduled APScheduler jobs, cron rows, run/stop, and background task conventions
globs:
      - backend/app/batch/*
      - backend/app/core/scheduler.py
      - backend/app/main.py
alwaysApply: false
---

# Batch Jobs

## The domain is four tables

`batch` is a folder domain, and each table answers a different question:

| Table | Answers |
|---|---|
| `batch_schedule` | which job runs, when, and whether the clock starts it |
| `batch_run` | when an execution ran and **how it ended** |
| `batch_step` | which unit inside a run did what — for a paging job, one window |
| `batch_checkpoint` | where the next run resumes — `NULL` when the job has no row cursor |

## The Checkpoint Is Optional, And It Stays At The Tail

`batch_checkpoint.next_range_start` is nullable, because a checkpoint is the
batch layer's common place to record where a job stopped and not every job stops
at a *row*:

| Job | Its position | Stored |
|---|---|---|
| `sync_barcode_ledger` | a row offset into a paged feed, and the key it was measured from | `next_range_start` + `last_row_key` |
| `purge_expired_refreshes` | a cutoff (`now - 30d`) | nothing — recomputed every run |
| `purge_old_batch_runs` | a cutoff (`now - 90d`) | nothing — recomputed every run |

`NULL` is "this source has no row cursor", which is a different fact from `1`
("start at the first row") — so the column carries no server default either, and
`find_checkpoint` hands back the row rather than inventing one job's first
window for every job. The caller decides what an unknown means for itself.

**A finished pass keeps its cursor at the tail**, so the next run asks for the
increment and a caught-up night costs one call instead of the 54 a restart
costs. Two rules keep it safe, and neither reads a count:

- **The end of a feed comes from the rows.** A page holding fewer records than
  its window asked for is the last one; a window sitting entirely past the end
  answers `INFO-200 해당하는 데이터가 없습니다`, either as an empty page or as a
  refusal, depending on whether the operation's contract lists that code. Both
  end the pass. `total_count` is *not* used: some operations on this portal
  report a fixed `1` whatever the set holds, so a walk that trusted it would
  stop after one page.
- **The offset is verified before it is trusted.** A run with a cursor re-reads
  one row it already consumed — the first window starts at `cursor - 1` — and
  compares that record's natural key with `last_row_key`. Same key, the walk
  continues; different key or nothing there, rows were removed or re-ordered and
  the walk restarts at row 1. It costs no extra call (the row rides in a page
  the run was fetching anyway) and no extra write (the ledger's upsert compares
  before it writes).

What that still does not catch is stated where it is decided
(`app/batch/sync_barcode_ledger.py`): an offset walk sees rows appended past the
cursor, never an edit to a record behind it.

A run's ending is one of five, and they are different facts:
`RUNNING` → `SUCCEEDED` | `FAILED` | `STOPPED` | `INTERRUPTED`.

`INTERRUPTED` has no writer of its own: a killed process cannot report
anything, so the next startup sweeps whatever is still `RUNNING`
(`BatchRunService.update_interrupted_runs`, called from the lifespan). Without
it a killed run claims to be running for as long as the table lives.

**Who writes what, and why it cannot be anyone else:**

| Moment | Writer | Why there |
|---|---|---|
| start | `BatchScheduler._run` | both cron and manual runs pass through it |
| `SUCCEEDED` / `FAILED` | `BatchScheduler._run` | it sees the return value and the exception |
| `STOPPED` | `BatchScheduler.stop` | measured: a write inside the cancelled task is itself cancelled — the row never landed and the stop took seconds |
| `INTERRUPTED` | lifespan sweep | nothing else survives the process |
| one step | the job | only the job knows its window and counts |

An ending is written **once**: `stop` and a job that finished anyway both
reach the row, and the first one wins — otherwise a stopped run would be
reported as successful.

**A job reads its run from `current_run_id`** (`app/services/batch/run.py`), a
contextvar the scheduler sets. `BATCH_JOBS` calls a job with no arguments, so
widening that signature would put the log in every job's contract; a job started
by hand finds `None` there and writes no steps.

**A step points at its call.** `batch_step.integration_call_id` joins to the
scrubbed request/response `integration_call` already stores, so a failed window
leads to the provider's own answer in one join. On the failure path the id comes
from `IntegrationOperationService.last_call_id`, because the raise carries no
return value.

**Logging never costs the work.** A run row that cannot be written is logged and
the job proceeds; an ending that cannot be written leaves the row open, and the
next startup calls that `INTERRUPTED` — which is exactly what it is.

## The schedule is a table, not a lifespan branch

`app/main.py` schedules nothing by name. The `batch` table is the job table:
one row per schedule, carrying `code` (which job), `cron` (when), and `enabled`
(whether the clock starts it). The lifespan reads every enabled row through
`BatchScheduleService.list_enabled_batches()` and hands each one to `BatchScheduler`.

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

## One Job, One Module, Named After It

`app/batch/<job_code>.py` — and the name is the same string four times:

```
app/batch/purge_old_batch_runs.py     the module
    async def purge_old_batch_runs    the function it exports
BATCH_JOBS["purge_old_batch_runs"]    the key that makes it runnable
batch_schedule.code = 'purge_old...'  the row that schedules it
tests/batch/test_purge_old_batch_runs.py
```

That chain is what makes a failed run navigable in one step: the log line names
the code, and the code *is* the path. It is the convention `models/` and
`repositories/` already carry (a file is named after the one thing it owns);
`app/batch/` was the layer that had no rule, and three files had drifted into
three different ideas — a plural domain (`refreshes.py`), a plural table
(`runs.py`, one letter from `models/batch/run.py`), and a plural noun
(`barcodes.py`). Each said which *data* the job touched; none said which job it
was.

Two public jobs in one module is rejected rather than renamed: both cannot be
the file's name.

## Batch Job Pattern (`app/batch/<job_code>.py`)

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
8. **A resume contract is whole or absent — and a NULL cursor is neither.** The
   checkpoint is every job's common place, so *reading* it proves nothing: a
   cutoff job may read its row, find no cursor, and recompute from the clock.
   What proves a row cursor is what the job does with the row — it consumes
   `next_range_start`, or it calls `update_resume_point` (an `int`, by
   signature). A job that consumes the cursor advances it in the same module,
   and one that advances reads first; a job that pages a feed (a provider
   called from inside a loop) asks its checkpoint at all — a cursor, a NULL
   row, or no row is its decision, and a walk that never asks decided nothing;
   a paging job records one step per window (`create_finished_step`) under the
   run it reads from `current_run_id`. Each half alone is a working call that
   resumes nothing

## Adding a New Batch Job

1. Create `app/batch/<job_code>.py`, holding one public `async def <job_code>`,
   following the pattern above — `make check-backend-batch` proves the shape
   (session-per-run, no HTTP-layer imports) and the name.
2. Register it in `BATCH_JOBS` (`app/core/scheduler.py`) under that same string,
   **alongside** the existing entries — registries accumulate
   (rule://backend-domain).
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
  `asyncio.Event`; poll `_is_running()` rather than sleeping a fixed time
  (`tests/core/test_scheduler.py`)

## Validation (Post-Hook)

`check-backend-batch.ts` enforces the whole chain, because every missing link
fails **silently** — each row below was reproduced by deleting the link and
watching the gate go red:

| Link | Checked | Without the check |
|---|---|---|
| the module is named after its job | one public `async def` per module, its name equal to the file stem | the file says which data the job reads, not which job it is — `runs.py` beside `models/batch/run.py` |
| the code is the function's name | `BATCH_JOBS` key equals the function it names | a row says `nightly_cleanup` and only this table says which Python that is |
| `app/batch/<job_code>.py` defines `async def <job>` | every **public** job function appears as a `BATCH_JOBS` value (a `_` helper is not schedulable) | an unregistered function is dead code nothing can schedule |
| `BATCH_JOBS` names a real function | every registry value is defined or imported | a code that resolves to nothing fails at 03:00, in the executor |
| a migration seeds the `batch` row | seeded codes are discovered from `op.bulk_insert` on `batch` — never a hardcoded list | a job that exists only in Python runs in no environment |
| `main.py` schedules nothing by name | `add_job(` is forbidden in `main.py` | a lifespan job cannot be rescheduled or stopped without a deploy |
| the lifespan reads the table | `main.py` calls `list_enabled_batches` | the process schedules whatever the last deploy hardcoded |
| the lifespan sweeps orphans | `main.py` calls `update_interrupted_runs` | a killed process's run claims RUNNING forever — `main.py` is outside coverage, so nothing else notices the deleted call |
| `core/scheduler.py` `add_job` carries `id` / `replace_existing` / `max_instances` / `coalesce` / `misfire_grace_time` | option by option | duplicated, overlapping, or silently skipped runs |
| a consumed cursor is advanced by the same job | `find_checkpoint` + `.next_range_start` ⇒ `update_resume_point`; `update_resume_point` ⇒ `find_checkpoint` | read-only re-walks the feed from the same position every night; write-only stores a cursor nothing resumes from |
| a paged feed asks its checkpoint | `execute_operation` inside a `for`/`while` ⇒ `find_checkpoint` (a NULL row or no row is a legitimate answer — reading only is fine) | a walk that restarts at row 1 without having decided to |
| a paging job records its windows | `execute_operation` in a loop, or `update_resume_point` ⇒ `create_finished_step`; `create_finished_step` ⇔ `current_run_id.get()` | a failed run says which job, never which window; a step written without the run in context belongs to none |

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
