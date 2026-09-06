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

## The Configuration A Job Names Must Exist

`PROVIDER_CODE` and `OPERATION_CODE` are resolved at 03:00 against
`integration_provider` / `integration_operation`. Nothing else in the stack ties
them to a row: the job type-checks, its tests script the seam and never look the
codes up, and a planted `search-ghost-material` left every gate green - measured.
The failure then surfaces once a night, in a scheduler log, as configuration that
does not exist.

So `check-backend-batch` reads the seeded codes out of `alembic/versions/` (not
out of the running database, so a fresh clone answers the same) and refuses a
sync job naming either code that no revision inserts. A maintenance job, which
calls no operation, is not asked.

**A code arrives two ways, and the check reads both.** Revision 74 renames a
provider (`mfds-food-nutrition` → `data-go-kr`) through
`provider.update().values(code=CODE)` with no insert anywhere, and the first
version of this check called `data-go-kr` unseeded on the nutrition job's very
first gate — a false positive against a row every migrated database carries. The
extractor now follows the rename, resolves one constant indirection, and drops
the code the downgrade restores: that one is no longer in any database, and
listing it would accept a job naming a provider that stopped existing.

## A PAGE Job Refuses Its Ceiling

A PAGE-family provider has a maximum `num_of_rows`, and exceeding it is silent:
measured on `search-food-nutrition`, 501 and up answer HTTP 200 with an empty
list — the same shape as the end of the feed. A job past the ceiling imports
nothing, stops on its "short" first page and reports success every night, and no
other gate sees it because the call succeeded.

So a job whose operation takes `num_of_rows` (read off the seeded caller inputs)
declares `MAX_PAGE_SIZE` and **refuses** a `page_size` above it — never clamps: a
caller asking for 900 believes it will get 900, and a silent narrowing keeps that
belief alive. A RANGE job is not asked; its provider refuses out loud (`ERROR-336`).

## The Ledger Reads Exactly What The Operation Answers

`from_record` is a list of `record.get("<key>")` calls over a `Mapping[str,
object]`, and nothing types the key: a misspelt one reads `None`, the column is
NULL on every record forever, and the run reports success. The reverse drift is
quieter — a key added to the seed that the ledger never reads is data the sync
drops.

`check-backend-batch` reads the operation's seeded `RESPONSE_ROWS` and checks
the ledger's schema both ways. A key the ledger declines on purpose (`row_no`,
the record's position inside its page) is declared in an `UNSTORED_KEYS`
frozenset beside `from_record`, with the reason — so a decline is a decision the
check can tell from a column that was forgotten. Measured on the first audit: all
three ledgers matched their contracts, and `row_no` was the only decline.

## A Check Names Things That Exist

`checkResumeContract` greps for `resume_position`, `find_checkpoint` and
`update_resume_point`. Renaming `next_range_start` left it green while it
recognised no job as consuming a cursor — every invariant it enforces switched
off, and only a planted violation showed it. A string check cannot survive a
rename; it can refuse to run blind, so the hook fails when the model or the
service no longer declares the names it looks for.

## A Migration Walks Positions, Never A Filter

The increment is the checkpoint's position - a row offset or a page number -
and nothing else. Every operation here seeds optional caller inputs beside its
paging keys (`change_date`, `changed_from`, `last_updated_from`, `update_date`,
a product name, a licence number), and each reads a **subset**. A job that sent
one would import what matched and call the ledger complete.

The temptation is measured, not hypothetical: `search-food-item-report` caps
unfiltered calls at 100 an hour and exempts the date filter, and the date
filter reads 5,800 rows where the feed holds 1,071,979. The answer is to pay the
quota in runs - which is what the checkpoint exists for - not to narrow the
walk.

`check-backend-batch` reads the operation's seeded caller inputs and fails a
sync job whose window carries any key outside the paging family. Audited on the
day the check landed: all four ledgers sent paging keys only (the nutrition
job's `type: json` was a seeded literal sent twice, and was dropped).

## A Quota Is Neither The End Nor A Failure

Measured on `search-food-item-report` (2026-09-05): the portal allows **100
unfiltered calls per hour per key** and answers `INFO-320 CHNG_DT 파라미터를
사용하지 않으면 1시간당 100회까지만 호출할 수 있습니다` past that. The feed is
1,072 windows (`total_count` 1,071,979), so a full pass is eleven nightly runs,
and the code arrives mid-walk on any night that walks past the quota.

Three readings were possible and two are wrong:

| Read as | Consequence |
|---|---|
| a failure (raise) | the initial load dies at window 101 every hour and never finishes |
| the end of the feed | the cursor lands at the tail of a half-imported set, and the next run reads only the increment |
| **a quota (stop, keep the cursor)** | the run ends where it is, the checkpoint still names the refused window, the next run opens it again |

So a job names its quota codes (`QUOTA_CODES`) beside its end-of-data codes,
and `DEFAULT_MAX_PAGES` is the quota, not a size guess: a ceiling above it
would not read more, it would end the run on a refusal instead of on its own
count. The migration still walks positions - a date filter reads only what
changed, and a migration is everything.

## Two Archetypes

Every job in `app/batch/` is one of two shapes, and the difference is what it is
incremental *by*. Both are machine-checked by `check-backend-batch`.

| | **Sync** — fills a ledger from a provider | **Maintenance** — keeps a table bounded |
|---|---|---|
| Example | `sync_food_barcode_ledger` | `purge_old_batch_runs`, `purge_expired_refreshes` |
| Increment | a position in the feed | time |
| Settings | `PROVIDER_CODE`, `OPERATION_CODE`, `DEFAULT_*PAGE_SIZE*`, `DEFAULT_MAX_*` | a retention/grace constant |
| Cursor | reads `find_checkpoint`, advances `update_resume_point` | none — a cutoff is recomputed from the clock |
| Per window | one step (`create_finished_step`) under `current_run_id` | no steps |
| Ends when | a short page, the end-of-data code, or the ceiling | the cutoff query returns nothing |

### Incremental Settings Are Named, And They Are Parameters

**Every knob is an `UPPER_SNAKE` module constant, and every knob is a parameter
of the job defaulted to it.** Both halves are checked:

- a parameter defaulting to a literal (`days: int = 30`) is a measurement with
  nowhere to record what it measured — found by this check in
  `purge_expired_refreshes`, which had 30 inline while its sibling had
  `DEFAULT_RETENTION_DAYS = 90`;
- a `DEFAULT_*` constant that is nobody's default is read directly by the job,
  which reads like a setting and behaves like a literal: an operator re-syncing
  one window would have to edit the module.

A sync job additionally states three things it cannot run without:

- **`PROVIDER_CODE` / `OPERATION_CODE`** — the job names configuration, never a
  URL. The path, the key, the filters and the paging family live in
  `integration_field`.
- **A window** (`DEFAULT_*PAGE_SIZE*`) — the provider caps how wide one call may
  be, and the cap is a measurement (I2570: 1000 rows; 1001 is accepted only
  because their validator compares `end - start`, so the extra row rides a bug).
- **A ceiling** (`DEFAULT_MAX_*`) — a provider that ignores a filter answers 200
  with a full unfiltered page forever, and an unbounded walk follows it until the
  process dies. It must still exceed the whole feed, because the cursor only
  advances when a pass reaches the end.

## A Job Names The Ledger It Fills

The identity chain — module = function = `BATCH_JOBS` key = seeded
`batch_schedule.code` — is self-consistent by construction, so it stays green
while the thing the job *writes* is renamed underneath it. Measured: the ledger
became `food_barcode` and `sync_barcode_ledger` kept a noun that named no table,
with all five names stale together and every gate passing.

So the job's name carries its subject, and `check-backend-batch` reads that
subject from the job's own imports: a **flat** `from app.services.<domain> import`
is what a job reaches its data through, while the services every job uses to
record itself arrive dotted (`app.services.batch.run`) and never match. No domain
name is listed in the check.

A renamed job code is a data migration, not just a rename: the schedule is a row
(`batch_schedule.code`), so Python alone would leave every environment running a
row whose code names a module that no longer exists. `seededBatchCodes()` reads
updates as well as inserts for the same reason — a renamed code is scheduled, and
a reader that knew only `bulk_insert` called it unseeded.

## The Checkpoint Is Optional, And It Stays At The Tail

`batch_checkpoint.resume_position` is nullable, because a checkpoint is the
batch layer's common place to record where a job stopped and not every job stops
at a position:

| Job | Its position | Stored |
|---|---|---|
| `sync_food_barcode_ledger` | a **row** offset into a RANGE feed, and the key of the last row it consumed | `resume_position` + `resume_key` |
| `sync_food_nutrition_ledger` | the **page** it imported in a PAGE feed, and that page's first record | `resume_position` + `resume_key` |
| `purge_expired_refreshes` | a cutoff (`now - 30d`) | nothing — recomputed every run |
| `purge_old_batch_runs` | a cutoff (`now - 90d`) | nothing — recomputed every run |

**One number, two units, and the column name says neither.** It was
`next_range_start` while every ledger walked rows; the page ledger then stored
page numbers under a name that said rows. The unit belongs to the feed, so the
column is `resume_position` and each job states its own — a second nullable
column per family would let one row claim both.

`NULL` is "this source has no cursor", which is a different fact from `1`
("start at the first row or page") — so the column carries no server default
either, and `find_checkpoint` hands back the row rather than inventing one job's
first window for every job. The caller decides what an unknown means for itself.

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
- **The position is verified before it is trusted.** A run with a cursor
  re-reads what it already consumed and compares a natural key with
  `resume_key`. Same key, the walk continues; different key or nothing there,
  records were removed or re-ordered and the walk restarts at the first
  position. It costs no extra call (the overlap rides in a window the run was
  fetching anyway) and no extra write (the ledger's upsert compares before it
  writes).

  **A mismatch re-anchors before it restarts.** The anchored record is looked
  for in the overlap window itself (records inserted before the cursor push it
  a few rows down - it is still there, at no extra call) and then in the one
  window behind it (records removed pull it up - one more call, one more step);
  only an anchor found in neither means the feed was re-ordered, and the walk
  starts over. Measured on I1250 (2026-09-06): three reports inserted somewhere
  in the first 191k rows moved the anchor from 190999 to 191002, and the
  restart that followed re-read 99 windows to write three rows. Against a
  1,072-window feed at 100 windows an hour, a restart on every small shift is an
  initial load that never finishes; with re-anchoring the next run resumed at
  99000, verified, and walked 99 windows (7,001 new rows) before the quota.
  Steps number the calls made, so a probe is a step of its own.

  **Which record proves the position is the paging family's answer, not the
  table's.** A RANGE walk starts one row early and compares that row: the row it
  consumed last. A PAGE walk re-reads the page it imported and compares that
  page's **first** record — new records are appended to the last page, so its
  last record changes on any ordinary night, and anchoring there would read
  every normal night as a re-ordered feed and re-import the whole set.

What that still does not catch is stated where it is decided
(`app/batch/sync_food_barcode_ledger.py`): an offset walk sees rows appended past the
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
   `resume_position`, or it calls `update_resume_point` (an `int`, by
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
| a consumed cursor is advanced by the same job | `find_checkpoint` + `.resume_position` ⇒ `update_resume_point`; `update_resume_point` ⇒ `find_checkpoint` | read-only re-walks the feed from the same position every night; write-only stores a cursor nothing resumes from |
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
