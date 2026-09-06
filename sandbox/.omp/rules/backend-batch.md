---
description: Backend batch jobs — database-scheduled APScheduler jobs, cron rows, run/stop, and background task conventions
globs:
      - backend/app/batch/*
      - backend/app/core/scheduler.py
      - backend/app/main.py
alwaysApply: false
---

# Batch Jobs

## The domain is three tables

`batch` is a folder domain, and each table answers a different question:

| Table | Answers |
|---|---|
| `batch_schedule` | which job runs, when, and whether the clock starts it |
| `batch_run` | when an execution ran and **how it ended** |
| `batch_step` | which unit inside a run did what — for a provider job, one window |

There is no fourth table. `batch_checkpoint` held where a job would resume
(revisions 89–98, dropped by 111), and it was the seat of most of this layer's
complexity: a cursor per feed, a key that verified it, re-anchoring when the
feed shifted, and a check that had to prove every job handled all three. The
feeds carry no change stamp to follow (every row of I2520 says `2015-01-22`),
so the increment was never real - and a pass that reads the whole feed every
night needs nowhere to resume from.

## The Configuration A Job Names Must Exist

`PROVIDER_CODE` and every feed's operation code are resolved at 03:00 against
`integration_provider` / `integration_operation`. Nothing else in the stack ties
them to a row: the job type-checks, its tests script the seam and never look the
codes up, and a planted `search-ghost-material` left every gate green - measured.
The failure then surfaces once a night, in a scheduler log, as configuration that
does not exist.

So `check-backend-batch` reads the seeded codes out of `alembic/versions/` (not
out of the running database, so a fresh clone answers the same) and refuses a
provider job naming a provider or a feed that no revision inserts. It also reads
each feed's paging family off the seeded caller inputs and refuses a tuple that
mixes them: one job asks every feed for the same window, so a RANGE feed and a
PAGE feed belong to different jobs. A maintenance job, which walks nothing, is
not asked.

**A code arrives two ways, and the check reads both.** Revision 74 renames a
provider (`mfds-food-nutrition` → `data-go-kr`) through
`provider.update().values(code=CODE)` with no insert anywhere, and the first
version of this check called `data-go-kr` unseeded on the nutrition job's very
first gate — a false positive against a row every migrated database carries. The
extractor now follows the rename, resolves one constant indirection, and drops
the code the downgrade restores: that one is no longer in any database, and
listing it would accept a job naming a provider that stopped existing.

## An Integration Target Is A Ledger

The checks above read a job and ask whether what it names exists. The reverse
question is the one that decides whether an integration is finished: **every
seeded operation that pages is a feed some provider job walks.** Seeding the
provider, the operation and its fields (`integration` skill) is the first half
of adopting a dataset; the table, its `replace_<table>_ledger` and the `Feed`
in `sync_<provider>_ledgers.py` (`ledger` skill) are the second half, and a
change that ships the first without the second leaves a feed the database
never holds. Measured on this tree: `search-product-classification` and
`search-test-item` were seeded and configured at revision 64, and for the whole
life of the five-jobs design no job read either — nothing asked. The day the
check first ran it named both; their ledgers are revisions 112 and 113, and
the first pass took 3,393 and 9,633 rows in 2.3 s and 4.9 s (2026-09-06).

Paging is the criterion, not existence. An operation whose caller inputs carry
no `range_start`/`page_no` is a lookup the API answers per call (a barcode, a
report number), and a lookup has no feed to replace a ledger with; it is not
asked for one. An operation that pages is a feed by construction — the portal
publishes it whole, in windows — and a feed that is not walked is data that was
worth seeding and not worth keeping, which is not a position anyone took on
purpose.

The pair is held both ways: a `Feed` names an operation of the job's own
provider (the walk resolves `(provider, operation)` together, and a feed of
another provider fails at 03:00 on configuration), and each seeded paging
operation appears in exactly the job of its provider — the operation's
provider is read off its seed's `PROVIDER_ID`, renames followed, so the
nutrition operations answer `data-go-kr` and not the code their seed string
still says.

## The Floor Refuses A Pass That Is Not A Feed

A provider's ceiling is silent on one family: measured on `search-food-nutrition`
(2026-09-05), `num_of_rows` of 501 and up answers HTTP 200 with an empty list —
the same shape as the end of the feed. A job past the ceiling reads nothing,
stops on its "short" first page and would report success every night, and no
other gate sees it because the call succeeded. (RANGE refuses out loud:
`ERROR-336` past 1000 rows.)

The seed carries no ceiling, so the guard is where the pass lands: `LedgerStage.
merge` refuses a pass **under the floor** (half the live rows, `DEFAULT_FLOOR`)
and refuses an **empty pass whatever the ledger holds** — a feed that answered
no rows at all is a window past the ceiling, not a first load, and the first
night is the one nothing else would catch. Either refusal raises
`LedgerFloorError` with both counts, the ledger stays as it was, and the feed's
night is FAILED. `PAGE_SIZE` is therefore the portal's measured cap, written
once per provider job with its evidence beside it, and never a parameter.

## The Ledger Reads Exactly What The Operation Answers

`from_record` is a list of `record.get("<key>")` calls over a `Mapping[str,
object]`, and nothing types the key: a misspelt one reads `None`, the column is
NULL on every record forever, and the run reports success. The reverse drift is
quieter — a key added to the seed that the ledger never reads is data the sync
drops.

`check-backend-batch` reads each feed's seeded `RESPONSE_ROWS` and checks the
schema of the table the feed's service names (`app/schemas/<domain>/<table>.py`)
both ways. A key the ledger declines on purpose (`row_no`,
the record's position inside its page) is declared in an `UNSTORED_KEYS`
frozenset beside `from_record`, with the reason — so a decline is a decision the
check can tell from a column that was forgotten. Measured on the first audit: all
three ledgers matched their contracts, and `row_no` was the only decline.

## A Check Names Things That Exist

Every ledger fact this harness knows comes from one reader,
`hooks/lib/backend-ledger-feeds.ts`, which parses the `FEEDS` tuple of each
`sync_<provider>_ledgers.py` into `{provider, operation, service,
replace, domain, table}`. The read-only router (`check-backend-domain`), the
ledger list screen (`check-frontend-screens`) and the frontend domain shape
(`check-frontend-domain`) all ask it, so a job may hold several ledgers and no
check derives a table from a file name. A `Feed(...)` the reader cannot place —
a service not imported from `app.services.<domain>.<table>` — is reported by
`check-backend-batch` rather than silently dropped, so the reader cannot go
blind on a rename the way the old cursor check did (measured: renaming
`next_range_start` switched every invariant off and stayed green).

## A Migration Walks Positions, Never A Filter

A pass is windows of `PAGE_SIZE` from the first row, and nothing else. Every
operation here seeds optional caller inputs beside its paging keys (`change_date`, `changed_from`, `last_updated_from`, `update_date`,
a product name, a licence number), and each reads a **subset**. A job that sent
one would import what matched and call the ledger complete.

The temptation is measured, not hypothetical: `search-food-item-report` caps
unfiltered calls at 100 an hour and exempts the date filter, and the date
filter reads 5,800 rows where the feed holds 1,071,979. The answer is to pay the
quota in hours - the walk waits it out - not to narrow the walk.

`check-backend-batch` reads each feed's seeded caller inputs and fails a
provider job whose module sends any key outside the paging family. Audited on the
day the check landed: all four ledgers sent paging keys only (the nutrition
job's `type: json` was a seeded literal sent twice, and was dropped).

## A Quota Is Neither The End Nor A Failure

Measured on `search-food-item-report` (2026-09-05): the portal allows **100
unfiltered calls per hour per key** and answers `INFO-320 CHNG_DT 파라미터를
사용하지 않으면 1시간당 100회까지만 호출할 수 있습니다` past that. The feed is
1,072 windows, so a pass walks past the quota every night.

Three readings were possible and two are wrong:

| Read as | Consequence |
|---|---|
| a failure (raise) | the load dies at window 101 every hour and never finishes |
| the end of the feed | the ledger is replaced with the first hundred windows |
| **a wait (sleep, ask the same window again)** | the pass takes the hours it takes, and the ledger is the whole feed |

The reading lives in one place, `IntegrationOperationService.walk_operation`:
a quota code is seeded on the operation, the key pool rotates to the next key
(`rotation_group`), and when the whole pool is exhausted the walk sleeps until
the earliest `retry_at` and asks for the same window. A job names no quota
code and counts no windows. Measured on the first cron night (2026-09-07):
the six 식품안전나라 feeds are 2,258 windows, and a pool of three keys walked
them in 6 h 05 m, waits included, with no window refused.

## Two Archetypes

Every job in `app/batch/` is one of two shapes, and the difference is whether
it is incremental at all. Both are machine-checked by `check-backend-batch`.

| | **Provider** — replaces ledgers with a provider's feeds | **Maintenance** — keeps a table bounded |
|---|---|---|
| Example | `sync_mfds_ledgers`, `sync_data_go_kr_ledgers` | `purge_old_batch_runs`, `purge_expired_refreshes` |
| Increment | none — every night is the whole feed | time |
| Settings | `PROVIDER_CODE`, `PAGE_SIZE`, `END_CODES`, `SYNCED_BY`, `FEEDS` | a retention/grace constant, as a parameter |
| Per window | one step (`create_finished_step`) under `current_run_id` | no steps |
| Ends when | a page shorter than the window, or the end code | the cutoff query returns nothing |
| Fails when | `IntegrationError` / `LedgerFloorError` on a feed — that feed's ledger stays, the rest run, the first failure is raised at the end | the service raises |

### A Knob Is Named, And It Is A Parameter

**Every knob is an `UPPER_SNAKE` module constant, and every knob is a parameter
of the job defaulted to it.** Both halves are checked:

- a parameter defaulting to a literal (`days: int = 30`) is a measurement with
  nowhere to record what it measured — found by this check in
  `purge_expired_refreshes`, which had 30 inline while its sibling had
  `DEFAULT_RETENTION_DAYS = 90`;
- a `DEFAULT_*` constant that is nobody's default is read directly by the job,
  which reads like a setting and behaves like a literal: an operator re-syncing
  one window would have to edit the module.

A provider job has **no knob and no parameter**. What it states are facts about
the portal, one each, and `check-backend-batch` requires all of them:

- **`PROVIDER_CODE`** — the job names configuration, never a URL. The path, the
  key, the filters and the paging family live in `integration_field`.
- **`PAGE_SIZE`** — the portal's cap on one call, measured and cited beside it
  (식품안전나라: 1000, `ERROR-336`; data.go.kr: 500, silent). One for every
  feed, and every `walk_operation` call passes `page_size=PAGE_SIZE`.
- **`END_CODES`** — what the portal answers past its last row (`INFO-200`), or
  empty when it answers a short page; every call passes `end_codes=END_CODES`.
- **`SYNCED_BY`** — `batch:<job>`, what the rows say wrote them.
- **`FEEDS`** — a tuple of `Feed(<operation>, <Service>,
  <Service>.replace_<table>_ledger)`, smallest feed first so a night that runs
  out of hours still finished something.

Nothing else: no `MAX_*`, no cursor, no `total_count` (some operations report a
fixed `1` whatever the set holds). The check refuses those names in code.

## A Job Names Its Provider

The identity chain — module = function = `BATCH_JOBS` key = seeded
`batch_schedule.code` — is self-consistent by construction, so it stays green
while the thing the job *reads* is renamed underneath it. Measured: the ledger
became `food_barcode` and `sync_barcode_ledger` kept a noun that named no table,
with all five names stale together and every gate passing.

A provider job holds several ledgers, so its name carries the provider, not a
table: `sync_<provider>_ledgers`, where `<provider>` is `PROVIDER_CODE` with
`-` as `_`, or its leading tokens (`mfds-food-safety-korea` →
`sync_mfds_ledgers`; `data-go-kr` → `sync_data_go_kr_ledgers`).
`check-backend-batch` holds the name to the code, and the tables a job fills are
read off `FEEDS`, never off the name.

A renamed job code is a data migration, not just a rename: the schedule is a row
(`batch_schedule.code`), so Python alone would leave every environment running a
row whose code names a module that no longer exists. `seededBatchCodes()` reads
updates as well as inserts for the same reason — a renamed code is scheduled, and
a reader that knew only `bulk_insert` called it unseeded.

## A Pass Is The Whole Feed, Merged Through A Stage

A ledger is our copy of a provider's feed, so the ledger after a pass *is* the
pass. Each feed is read from row 1 in windows of `PAGE_SIZE` until a page comes
back short (or the portal answers `END_CODES`), every page is staged as it
arrives, and the ledger is then made equal to the stage in three set statements
(`app/core/ledger.py`, `LedgerStage`):

| Statement | Rows |
|---|---|
| `DELETE` | in the ledger, not in the pass |
| `UPDATE` (`version + 1`) | in both, and a synced column differs (`IS DISTINCT FROM`) |
| `INSERT` | in the pass, not in the ledger |

Why a stage and not a transaction around the walk: a pass over a million rows
spans hours and quota waits, and a reader must see the old ledger or the new
one, never a mix. The stage is a `TEMP` table, which lives on the connection
that created it — so the ledger session is pinned to one connection
(`AsyncSession(engine.connect())`, refused otherwise) and the calls get a
session of their own. `create()` drops a stage a dead pass left behind.

Why rows keep their `id`: the merge updates in place, so a bookmark that one day
joins a ledger row does so by natural key and never needs deleting.

Every feed's service exposes `replace_<table>_ledger(pages, synced_by, *,
floor)` and nothing else writes a ledger; it returns `(received, changed)`, and
the job returns the changes summed over its feeds (`written`). A record with no
natural key is skipped where it is read, so the same sparse row cannot be
inserted twice.

**A finished feed is its ledger's night, and a failed feed is not the run's.**
The job catches `IntegrationError` and `LedgerFloorError` per feed, leaves that
ledger as it was, goes on to the next, and raises the first failure once every
feed had its turn — so the run reads FAILED and the other ledgers are still
tonight's.

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
8. **A walked feed leaves steps, and a step belongs to the run in context.** A
   job that calls `walk_operation` records one step per window
   (`create_finished_step`) under the run it reads from `current_run_id`; a job
   that reads the run writes steps under it, and one that writes steps reads
   the run. Steps are numbered across feeds, and a refusal is a FAILED step
   naming the window it would have been. `written` stays empty on a step: a
   merge changes rows per feed, not per window
9. **A provider job is one rule for every feed.** `sync_<provider>_ledgers.py`
   states `PROVIDER_CODE`, `PAGE_SIZE`, `END_CODES`, `SYNCED_BY` and `FEEDS`,
   asks every walk for the same window and end codes, replaces every feed
   through its table's `replace_<table>_ledger`, and catches
   `LedgerFloorError` beside `IntegrationError` so feeds fail alone
10. **An integration target is a ledger.** Every seeded operation whose caller
    inputs page (`range_start` / `page_no`) is a `Feed` of its provider's job,
    and every `Feed` names an operation of that provider. Seeding a paging
    operation without its table and `Feed` is half an integration, and the
    check says which job the missing half belongs in

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
| a walked feed leaves steps | `walk_operation` ⇒ `create_finished_step`; `create_finished_step` ⇔ `current_run_id.get()` | a failed run says which job, never which window; a step written without the run in context belongs to none |
| a provider job has the provider shape | `sync_<provider>_ledgers.py` with `PROVIDER_CODE`/`PAGE_SIZE`/`END_CODES`/`SYNCED_BY`/`FEEDS`, name held to the code, no `MAX_*`/cursor/`total_count` in code | five settings drift five ways, and a ceiling or a count comes back as a "guard" that hides the floor |
| every feed replaces its own table | `Feed(op, Svc, Svc.replace_<table>_ledger)` where `Svc` is imported from `app.services.<domain>.<table>` | a feed replaced through another table's method, or outside `LedgerStage`, has no floor |
| every walk asks the same window | each `walk_operation` call passes `page_size=PAGE_SIZE` and `end_codes=END_CODES` | one feed pages alone and reads its end differently |
| the provider and every feed are seeded, and page alike | codes read from `alembic/versions/`; families read from seeded caller inputs | configuration that does not exist fails at 03:00; a RANGE feed asked for `page_no` reads nothing |
| every feed is the job's provider's | each `Feed` operation's seed names the job's `PROVIDER_CODE` (renames followed) | `(provider, operation)` resolves to no row, once a night |
| every seeded paging operation is a feed | configured operations with `range_start`/`page_no` among caller inputs ⇔ a `Feed` in some `sync_*_ledgers.py`; the message names the job it belongs in | an integration is "done" at the seed, and the dataset it was seeded for is never held |
| the ledger reads what its feed answers | `record.get("key")` in `app/schemas/<domain>/<table>.py` ⇔ seeded response keys, minus `UNSTORED_KEYS` | a misspelt key is NULL forever; a new key is dropped |
| a pass walks positions | no seeded caller input outside the paging keys is sent | a filter imports a subset and calls it the ledger |
| feeds fail alone | `LedgerFloorError` is caught in a job that walks | one feed's bad night empties nothing but ends every other feed's night too |

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
