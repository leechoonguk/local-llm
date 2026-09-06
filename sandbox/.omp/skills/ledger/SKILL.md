---
name: ledger
description: Adopt a seeded provider operation into a local table as one feed of its provider's nightly sync job - measure the whole feed, build the layers, add the Feed, and prove it with row counts from a live pass. Use when the user asks to migrate an external feed into a table, add a sync/batch job for a provider operation, or extend an existing ledger.
---

# Provider Feed → Ledger

`integration` ends where this begins: the provider, the operation and its fields
are seeded rows, and one recorded fixture proves the response shape. This skill
is the order the *ledger* work has to happen in — a table, a `Feed` in the
provider's job, a schedule row if the provider is new — and the traps that were
measured on the way.

The deliverable is **numbers from a live pass**, not a green suite. A suite
scripts the provider; only a real run meets the data.

## Workflow

### 1. Start from configuration that exists

```bash
make db-query q="SELECT o.code, o.method, o.path_template, p.code AS provider
  FROM integration_operation o JOIN integration_provider p ON p.id = o.provider_id"
make db-query q="SELECT f.direction, f.key, f.wire_path, f.value_type, f.required
  FROM integration_field f JOIN integration_operation o ON o.id = f.operation_id
  WHERE o.code = '<operation>' ORDER BY f.direction, f.ordinal"
```

The RESPONSE `key` list is the ledger's column list — one concept, one key, from
the wire through the table. A column the seed does not name is a column the sync
cannot fill. If the operation is not seeded, stop and run the `integration`
skill first: `check-backend-batch` refuses a job whose `PROVIDER_CODE` or a
`Feed` operation no migration inserts. The same check asks the reverse - every
seeded operation that pages must be a `Feed` of its provider's job - so a red
`make verify` naming an operation and a job is this skill's starting point, and
lists what is missing (`backend-batch.md`, "An Integration Target Is A Ledger").

**The REQUEST list decides which provider job the feed belongs in.** Two paging
families exist here (`paging_family` in `core/integration.py`):

| Family | Inputs | Window |
|---|---|---|
| RANGE | `range_start`, `range_end` | a row interval, `PAGE_SIZE` wide |
| PAGE | `page_no`, `num_of_rows` | a page number, `PAGE_SIZE` rows |

`search-food-raw-material` is RANGE; `search-food-nutrition` is PAGE. The walk
(`IntegrationOperationService.walk_operation`) reads the family off the seeded
inputs and computes the windows, so a job never names a family — but **one job
walks one provider, and every feed of a provider shares its family, its
`PAGE_SIZE` and its `END_CODES`**. A feed whose family differs from its
siblings' is a different portal, and gets a job of its own.

### 2. Measure the page ceiling **before** the walk

A PAGE feed has a maximum `num_of_rows`, and exceeding it is not an error:

```
num_of_rows=100 → 100 rows      num_of_rows=501  → 0 rows, HTTP 200
num_of_rows=500 → 500 rows      num_of_rows=1000 → 0 rows, HTTP 200
```

Measured on `search-food-nutrition` (2026-09-05). **An over-wide window answers
with the same shape as the end of the feed**, so a job configured at 1000 would
import nothing and stop on its "short" first page. Bisect the ceiling and make it
the provider job's `PAGE_SIZE`, the one width every feed of that job is walked
at. The floor is the guard behind the ceiling: `LedgerStage.merge` refuses an
empty pass whatever the ledger holds, so the misconfigured night fails loudly
instead of reporting success.

A RANGE feed has the same ceiling with a louder answer (`ERROR-336`), which is
why this trap belongs to the page family in particular.

**Also measure how many calls an hour buys.** `search-food-item-report` allows
100 unfiltered calls per hour (`INFO-320`), against a 1,072-window feed.

**A walk that ends on a refusal has not measured the end.** The measuring walk
of that feed stopped at 194 calls on `INFO-320`, and the first write-up called
194,000 "the whole feed" - it was the quota. The provider's `total_count` said
1,071,979 the whole time - and some of this portal's operations report a fixed
`1`, which is why nothing reads `total_count`: the walk ends on a *short page*
and on nothing else. A quota answer (`INFO-320`, the portal's `retry_at`) is
neither an end nor a failure: the walk rotates to the next key of the pool
(`integration_secret.rotation_group`) and, with every key spent, sleeps until
the earliest `retry_at` and asks for the same window again. A full pass of this
portal is 2,258 windows; at 100 calls an hour per key it is 6 h 05 m with three
keys, all of it inside one run (first cron night, 2026-09-07). The walk that
measured the widths spent the quota, so the first live run waited an hour on
window 1 - which is the right behaviour.

**Do not turn the migration into a date filter to dodge the quota.** A
`change_date` filter reads what changed (measured: 5,800 rows since 9/1 against
1,071,979), and the portal refuses dates older than a few days (`ERROR-303` at
8/25, accepted at 8/31). A migration is everything; the quota is paid in runs.

### 3. Measure the **whole** feed before choosing a column type

Not the first page. Walk it and take the maxima:

```python
# backend/.venv/bin/python — IntegrationOperationService is the seam the job uses
widths = collections.Counter(); total = 0
while True:
    result, _ = await svc.execute_operation(PROVIDER, OPERATION,
        {"range_start": start, "range_end": start + 999}, actor="probe")
    rows = result.canonical_payload
    rows = rows if isinstance(rows, list) else [rows]
    total += len(rows)
    for r in rows:
        for k, v in r.items():
            if isinstance(v, str): widths[k] = max(widths[k], len(v))
    if len(rows) < 1000: break
    start += 1000
```

Measured on I2520 (2026-09-05), and this is the trap:

| Range measured | `raw_material_alias` | `scientific_name` | `english_name` |
|---|---|---|---|
| first 3,000 rows | 94 | 225 | 242 |
| whole feed (43,609 rows) | **1130** | 311 | 272 |

`String(200)` was chosen from the first sample and rejected a record on the first
live pass; `String(1000)` was chosen from the first 3,000 and was exceeded deeper
in. **A rejected INSERT fails the whole page, not the row** — the window is one
transaction — so a bound that is one character short costs the night's run.

- A column that holds a *list* the provider joins into one string (aliases,
  synonyms, English/scientific names) is `Text`. Its length is an editorial
  choice nobody publishes, and `Text` stores identically to `VARCHAR` in
  Postgres, so the bound buys nothing but the outage.
- A column that holds a code, a flag or a date text keeps its bound: there the
  bound is the contract, and a violation is a contract change worth failing on.
- A column that holds a **measurement** is `Numeric`, and the parser strips what
  the portal writes into it: `1,000.000` (thousands separators, measured on the
  nutrition feed) raises `InvalidOperation` in a bare `Decimal(text)` and would
  refuse the 500-record page one comma arrived in.
- Write the measurement into the model beside the column, with its date and row
  count. The next reader needs the number, not the conclusion.

Also record the total: the floor (`DEFAULT_FLOOR`, half the live rows) is
judged against it, and a feed that legitimately halves is news the model's
docstring should have predicted.

### 4. Build the layers by copying the nearest ledger

**Every key the operation answers is read or declined.** `check-backend-batch`
diffs `from_record`'s `record.get(...)` keys against the seeded `RESPONSE_ROWS`
both ways; a key the ledger drops on purpose goes in `UNSTORED_KEYS` with its
reason. A typo in a key is otherwise a column that is NULL forever under a green
gate.

**When the operation answers more than ~50 columns, generate them from the seed
rather than typing them.** `integration_field` already holds the canonical key
list; a generator that emits the model and the schema from it cannot disagree
with the contract, and a hand-typed 193-column model would.

**A feed whose measurements are numbered on the wire (`AMT_NUM1..157`) reads like
the repeating group `backend-table-design.md` sends to a child table.** Argue it
with numbers, in the model's docstring, before choosing wide: each column is a
different quantity with its own unit (`energy_kcal`, `protein_g`), and as rows
the nutrition feed is 319,060 foods x ~70 filled measurements ≈ 22M records
upserted one by one every night. Wide won there; a feed with genuinely repeated
values of one meaning would not.

`models/food/barcode.py` and its siblings are the worked example. The natural key
is whatever the provider identifies a record by — one column (`raw_material_code`)
or a pair (`(barcode_no, report_no)`) — and it is `unique`, because the merge
joins the stage to the ledger on it and nothing else. The service exposes one
method, `replace_<table>_ledger(pages, synced_by, *, floor)`, that stages every
page of the walk into a TEMP table and merges it (`core/ledger.py`); the row
ids survive a pass, so a bookmark joined by natural key stays valid.

**When the domain gains its second table, the layers become folders.** Three
checks say so, in this order:

```
check-backend-repository-files  repositories/: food owns 2 files → repositories/food/
check-backend-model-files       models/: same
check-backend-domain            food_barcode: services layer exists but no model file
```

Move `models/`, `repositories/`, `schemas/`, `services/` **and** the mirrored
tests into `<domain>/`, then repoint every import. A folder domain needs no root
entity: `FoodBarcode*` and `FoodRawMaterial*` with no `Food*` is a complete
answer (`backend-domain.md`).

Shared decoding — a portal's timestamp convention, its empty-string handling —
goes in `core/`, not in a schema: the schema layer's public surface is its
Pydantic classes plus `to_read`/`to_read_list`, and `check-backend-domain`
enforces it. There is no `utils/` to put it in, and opening one would create a
home no check governs.

**Name that module after the source, not the domain.** `core/mfds_source.py`,
because what it knows is one portal's wire dialect; called `food_source.py` it
reads as a fact about the ledger and has to be renamed the first time another
domain of the same portal arrives.

### 5. The feed, the job, and the schedule row

**A feed is one line.** The provider's job already exists
(`app/batch/sync_<provider>_ledgers.py`, e.g. `sync_mfds_ledgers.py`); add a
`Feed(operation_code, Service, Service.replace_<table>_ledger)` to its `FEEDS`
tuple, smallest feed first, so a night that runs out of quota still finished
something. The job walks every feed whole, every night: the feed moves under a
walk (I1250 gained three rows overnight, inserted before the cursor), and a pass
that reads everything and replaces the ledger as a set has no cursor for it to
move under. There is no checkpoint, no resume and no `total_count` - the
`batch_checkpoint` table of revisions 89-98 was dropped in 111 with them.

**A new provider is a new job.** Copy `sync_mfds_ledgers.py` whole and change
the four facts (`PROVIDER_CODE`, `PAGE_SIZE`, `END_CODES`, `SYNCED_BY`) and the
`FEEDS`; the job's name token must be the provider code or its prefix
(`sync_data_go_kr_ledgers` ↔ `data-go-kr`). Then **both** registrations, in the
same change:

- `core/scheduler.py`: `BATCH_JOBS["<job_code>"] = <job_code>` — the key is the
  function's own name.
- A migration seeding one `batch_schedule` row. A job in no database runs in no
  environment; `check-backend-batch` fails a code no revision seeds.

Each feed is one `batch_step` (calls, rows received, rows changed); feeds fail
alone, and the first failure is raised after the last feed ran, so a floor
refusal on one ledger never costs the others their night.

Space the cron from its siblings when they share a credential: two jobs reading
one portal at 02:00 would make one of them fail every night for a reason neither
can report.

### 6. Tests, then the live pass

Three files, and they answer different questions:

| File | Proves |
|---|---|
| `tests/core/test_<convention>.py` | the wire readings (timezone, sparse columns) |
| `tests/services/<domain>/test_<table>.py` | the replace: the ledger equals the pass, a keyless record is skipped |
| `tests/batch/test_<job_code>.py` | one step per feed, feeds fail alone, the floor is caught, the run contract |

The batch test scripts `IntegrationOperationService.execute_operation` against an
in-memory engine (`tests/batch/scripted.py`) — the job's contract is which
windows it asks for and what it does with the answers, never the network. A new
feed of an existing provider needs no new batch test file: extend the
provider's.

**Copying a sibling's test file copies its measured facts.** Grep the copy for
numbers (`53k rows`, a date, a row count) and replace every one with this feed's
own, or delete the claim. A fabricated measurement in a docstring outlives the
person who copied it.

Then run it for real, and report the numbers:

```
first pass:   received: 43609  changed: 43609   (44 calls, 129s)
second pass:  received: 43609  changed: 0       max(version) = 1
stored:       max(length(raw_material_alias)) = 1130
```

`changed: 0` with `max(version)` unchanged is the merge contract: every row was
staged, compared (`IS DISTINCT FROM`), and left alone. A second pass that
changes rows the portal did not change means the comparison is broken, and
`updated_at` stops meaning "the portal changed this".

### 7. Gate

```bash
make verify
```

## Never Do These

- **Take the first page's widths as the contract.** Two bounds were chosen that
  way and both were exceeded further down the feed.
- **Hand-write a revision.** `make -C backend migrate-gen m="<real message>"`,
  then edit the generated body.
- **Leave a dead intermediate revision unpushed.** Widening 200 → 1000 → `Text`
  is one decision; unpushed, it collapses into one revision. Schema history
  should not record a bound that was never right.
- **Report a passing suite as proof.** The suite scripts the provider. Row
  counts from a live pass are the evidence.
- **`migrate-down` past the ledger's `create_table` to revise an earlier
  unpushed revision.** The downgrade drops the table, and the rows a day of
  quota paid for go with it - measured 2026-09-06: 1,072,054 rows, seven hours
  of three keys, gone to re-seed a quota code two revisions back. Revise the
  earlier revision, then re-apply it with a *new* revision that carries the
  same change forward, or accept the reload before typing the command.
- **Drive a live pass by calling the job function.** No `batch_run`, no
  `batch_step`: a restart in the middle of the night leaves no trace to read
  the morning after. `POST /batch/{id}/run` is the path that records, and the
  one the scheduler uses.
- **Name a provider or operation code the migrations do not seed.** It
  type-checks, its tests pass, and it fails once a night at 03:00 —
  `check-backend-batch` refuses it, because everything else stayed green.
  (`search-food-nutritional` for `search-food-nutrition` is exactly the typo it
  catches.)
- **Put a feed of another paging family, width or end code into a provider's
  job.** The job has one `PAGE_SIZE` and one `END_CODES`; a feed that needs
  others is another portal's, and `check-backend-batch` refuses the mix.
- **Add a cursor, a checkpoint or a `total_count` back.** Every one of them was
  built here and measured wrong (a moving feed, a fixed `1`, a stale anchor);
  the pass is the whole feed, and the retired names are refused by
  `check-backend-batch`.
