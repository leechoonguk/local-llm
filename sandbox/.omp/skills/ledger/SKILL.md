---
name: ledger
description: Adopt a seeded provider operation into a local table with a nightly sync batch job - measure the whole feed, build the five layers, seed the schedule, and prove it with row counts from a live pass. Use when the user asks to migrate an external feed into a table, add a sync/batch job for a provider operation, or extend an existing ledger.
---

# Provider Feed → Ledger

`integration` ends where this begins: the provider, the operation and its fields
are seeded rows, and one recorded fixture proves the response shape. This skill
is the order the *ledger* work has to happen in — a table, a sync job, a
schedule row — and the traps that were measured on the way.

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
skill first: `check-backend-batch` refuses a job whose `PROVIDER_CODE` /
`OPERATION_CODE` no migration inserts.

**The REQUEST list decides the whole shape of the job.** Two families exist here
and they are not interchangeable:

| Family | Inputs | Cursor | Overlap |
|---|---|---|---|
| RANGE | `range_start`, `range_end` | next **row** offset | one row, inside the page the run wanted anyway |
| PAGE | `page_no`, `num_of_rows` | last **page** imported | that whole page, re-read on resume |

`search-food-raw-material` is RANGE; `search-food-nutrition` is PAGE. Copying a
RANGE job onto a PAGE feed produces a job that type-checks, passes its tests
against a scripted provider, and walks the wrong positions against the real one.

### 2. Measure the page ceiling **before** the walk

A PAGE feed has a maximum `num_of_rows`, and exceeding it is not an error:

```
num_of_rows=100 → 100 rows      num_of_rows=501  → 0 rows, HTTP 200
num_of_rows=500 → 500 rows      num_of_rows=1000 → 0 rows, HTTP 200
```

Measured on `search-food-nutrition` (2026-09-05). **An over-wide window answers
with the same shape as the end of the feed**, so a job configured at 1000 would
import nothing, stop on its "short" first page, and report success every night.
Bisect the ceiling, make it the job's `DEFAULT_PAGE_SIZE`, and have the job
*refuse* a larger one rather than clamp it — a caller asking for 900 believes it
will get 900.

A RANGE feed has the same ceiling with a louder answer (`ERROR-336`), which is
why this trap belongs to the page family in particular.

**Also measure how many calls an hour buys.** `search-food-item-report` allows
100 unfiltered calls per hour (`INFO-320`), against a 1,072-window feed.

**A walk that ends on a refusal has not measured the end.** The measuring walk
of that feed stopped at 194 calls on `INFO-320`, and the first write-up called
194,000 "the whole feed" - it was the quota. The provider's `total_count` said
1,071,979 the whole time. So the walk's loop ends on a *short page*; any other
ending is a quota or a fault, and the total then comes from `total_count` where
the operation reports a truthful one (some of this portal's report a fixed `1` -
compare it against a page before trusting it). The walk
that measured the widths spent the quota, so the first live run of the job
answered `INFO-320` on window 1 and ended cleanly with nothing to resume from -
which is the right behaviour, and the reason a quota is its own code in the job
(`QUOTA_CODES`: stop, keep the cursor) rather than an end or a failure.

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

Also record the total: it is the ceiling's justification
(`DEFAULT_MAX_PAGES × DEFAULT_PAGE_SIZE` must exceed the whole set with room).

### 4. Build the five layers by copying the nearest ledger

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
or a pair (`(barcode_no, report_no)`) — and it is `unique`, because the upsert
matches on it and nothing else.

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

### 5. The job, the registry, and the schedule row

**Measure whether the feed moves under the cursor.** Read the same window on
two days and compare the first key. I1250 moved by three rows overnight
(inserts before the cursor); a job that restarted at row 1 on every shift
would never finish a 1,072-window load at 100 windows an hour. The RANGE jobs
re-anchor first - the overlap window, then one window back - and restart only
when the anchor is in neither.

`app/batch/<job_code>.py`, named after the ledger it fills. Copy the nearest sync
job of **the same paging family**: the resume contract (`find_checkpoint` →
`update_resume_point`), the step per window, the overlap that verifies the cursor
still means what it meant.

**On a PAGE feed the anchor is the resumed page's *first* record.** New records
are appended to the last page, so that page's *last* record changes on any
ordinary night — anchored there, every run would read the change as a shifted
feed and re-import the whole set. The first record moves only when records are
removed or re-ordered, which is exactly what the anchor exists to detect. The
cursor names the page the run imported, not the one after it, so the re-read is
the overlap and costs no extra call.

The step log still speaks in **rows** (`range_start`/`range_end` computed from
the page), so a reader comparing two ledgers' runs is comparing one unit.

Then **both** registrations, in the same change:

- `core/scheduler.py`: `BATCH_JOBS["<job_code>"] = <job_code>` — the key is the
  function's own name.
- A migration seeding one `batch_schedule` row. A job in no database runs in no
  environment; `check-backend-batch` fails a code no revision seeds.

Space the cron from its siblings when they share a credential: two jobs reading
one portal at 02:00 would make one of them fail every night for a reason neither
can report.

### 6. Tests, then the live pass

Three files, and they answer different questions:

| File | Proves |
|---|---|
| `tests/core/test_<convention>.py` | the wire readings (timezone, sparse columns) |
| `tests/services/<domain>/test_<table>.py` | the upsert: insert, compare, refresh, refuse a keyless record |
| `tests/batch/test_<job_code>.py` | paging, the ceiling, resume, the moved-feed restart, steps |

The batch test scripts `IntegrationOperationService.execute_operation` against an
in-memory engine — the job's contract is which windows it asks for and what it
does with the answers, never the network.

**Copying a sibling's test file copies its measured facts.** Grep the copy for
numbers (`53k rows`, a date, a row count) and replace every one with this feed's
own, or delete the claim. A fabricated measurement in a docstring outlives the
person who copied it.

Then run it for real, and report the numbers:

```
first pass:   written: 43609        (44 calls, 129s)
second pass:  written: 0            max(version) = 1   ← re-read window rewrote nothing
checkpoint:   next_range_start = 43610, last_row_key = 'Z0000000000000'
stored:       max(length(raw_material_alias)) = 1130
```

`written: 0` with `max(version)` unchanged is the incremental contract: the
overlap row was matched, compared, and left alone. A second pass that writes
rows means the comparison is broken, and `updated_at` stops meaning "the portal
changed this".

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
- **Name a provider or operation code the migrations do not seed.** It
  type-checks, its tests pass, and it fails once a night at 03:00 —
  `check-backend-batch` refuses it, because everything else stayed green.
  (`search-food-nutritional` for `search-food-nutrition` is exactly the typo it
  catches.)
- **Copy a sibling job across paging families.** A RANGE job on a PAGE feed
  passes its own scripted tests and walks the wrong positions against the real
  provider.
