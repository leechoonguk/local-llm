---
name: integration
description: Add or change a database-managed external API integration end to end - measure the provider, seed the configuration, prove it with a request file and a recorded contract fixture. Use when the user asks to integrate an external API, add a provider or operation, or change an existing integration's fields, paging, or response contract.
---

# External API Integration

The configuration lives in the database (`backend-integration-configuration.md`);
this skill is the order the work has to happen in, and the traps that were
measured on the way. **Measure the provider before designing anything** — every
rule below exists because a guess was wrong once.

## Workflow

### 1. Measure the provider first

Run the probe. It makes the calls and prints what they answered:

```bash
make probe-external-api url='https://host/api/KEY/SERVICE/json/{start}/{end}' \
  filter='FILTER_KEY=값' since='DATE_KEY=20240101'
```

It reports, per call, the HTTP status, the wrapper's verdict code and message,
`total_count`, the row count, the row's column list, and the one comparison the later
gates cannot make: the filter's total as a **path segment** against the same filter as
a **query string**.

**Do not narrate measurements.** Asked to run these calls by hand, an agent reported
four successful calls as throttled, inverted the empty-page case, claimed the provider
accepted a dashed date that actually answers `ERROR-601`, and miscounted the columns.
Seeding from that table would have produced a silently unfiltered operation that every
gate passes. Run the target, read its table, paste the numbers into the seed docstring.

For a provider the probe does not fit (a different envelope, a cursor, a POST body),
call it with `curl` and record the answers. Six questions, all of which changed a design decision:

| Question | Why it decides something |
|---|---|
| Does HTTPS work? | `base_url` must be an HTTPS origin; the API refuses anything else |
| Where does the key travel? | header, query, or **path segment** — the field's `location` |
| How does it page? | page number + size (`PAGE`), row interval (`RANGE`), or not at all |
| What is the success shape? | which node holds the records → `response_root` |
| What does an **empty** result look like? | absent collection, empty array, or a code |
| What does a **failure** look like? | HTTP status, or HTTP 200 with a code in the body wrapper |

Then ask the two questions that catch silent failures:

- **Do filters actually filter?** Send one and compare the total against no
  filter. Measured on I1250: `?PRDLST_NM=김치` is accepted and **ignored**
  (unfiltered count), while `/PRDLST_NM=김치` filters. A parameter the provider
  ignores looks exactly like a working one.
- **Does the window actually move?** Two calls, same size, different position,
  and compare the first record. A key with sample-only access returned the same
  five rows for every window.

**Measure per operation, never per provider.** Two services of one portal disagreed on
both counts that matter: a zero start index is `ERROR-331` on I1250 and accepted on
I2510, and a malformed date answers `ERROR-601` ("SQL 문장 오류") on I1250 while
I2530 answers the documented `ERROR-302` for the same input. A provider is a host and a credential; the contract
is per operation.

**A provider may refuse by the clock, and it refuses everything.** Measured on
`openapi.foodsafetykorea.go.kr`: between 09:00 and 19:00 KST every service answers
HTTP 200 with `ERROR-503 09시~19시에는 서비스가 일시적으로 원활하지 않을수있습니다` —
a service already seeded and working, and the documented **sample key** too. So a
blanket refusal is not a bad key: the key was already proven by the code changing
from `INFO-100 인증키가 유효하지 않습니다` to `ERROR-503`. Two facts follow:

- do not seed from a window you could not measure — a success shape guessed from
  the vendor page is exactly what step 1 exists to prevent;
- schedule the measurement instead of narrating it. `bash` with `sleep` until the
  window opens costs one background job, and the probe then reports real numbers
  (I2530 at 19:01: `INFO-000`, `total_count` 3393, the window moving and resizing,
  `LAST_UPDT_DTM=20200318` filtering to 116 as a path segment and being ignored as
  a query string).

**When a seed problem names a database constraint, reset before diagnosing.** A
half-applied migration chain reports defects the migrations do not have: measured
here as `uq_integration_operation_provider_code` on a re-upgrade, which read like a
seed inserting a duplicate and was a database whose version pointer no longer
described its rows. `make db-init` is one command, and the same chain then steps
down cleanly to the first revision (`rule://backend-migrations`).

### 2. Derive the shape from the measurements

- `response_root` — absent maps one record through absolute pointers; a pointer
  at an array maps **every element**, and each `RESPONSE` row's `wire_path` is
  relative to one element. A paging operation must name the page and must never
  pin an index (`/body/items/0` returned one record however large the page was).
- Paging inputs are `CALLER`, `required`, with **no** `value`, and they are one
  whole family (`PAGE` or `RANGE`) or none.
- Every provider response column the caller may read gets a row carrying `key`,
  `wire_path`, `value_type` and the provider's own `description`. The key comes
  from the description, not the wire name; the printed unit becomes the suffix
  (`AMT_NUM1`/에너지(kcal) → `energy_kcal`).
- Exactly one `required` `RESPONSE` row — the field that makes the record that
  record. Sparse columns arrive as empty strings and would turn a normal answer
  into a 502.
- If the provider answers HTTP 200 for failures, add `ENVELOPE` rows: one with a
  `match_mode` listing the codes that mean success, and unchecked ones for the
  values worth surfacing (`total_count` is what a paged caller needs).
- One concept, one key across both directions: `MAKER_NM` is `maker_name` going
  out and coming back. A **bound is not a value**, though: I2510's `LAST_UPDT_DTM`
  filter selects rows changed on or after a date, so it is `last_updated_from` on the
  way out and `last_updated_at` on the way back. Sharing one key would claim they are
  the same thing.
- The envelope row lists the codes that mean **success**, not the codes that mean
  failure. Measured: this provider answers with codes its own documentation does not
  list, and a failure list would have passed `ERROR-601` through as success.

### 3. Seed it, one table per migration

First decide whether the provider already exists. A provider is one host and one
credential, so a second service of the same portal **reuses both** — seed only the
operation and its fields, and reference the existing secret through the same `uuid5`
seed string. Duplicating the provider would duplicate the key, which then has to be
rotated twice.

Order matters, because a provider replace cascades its operations away and an
operation replace cascades its fields:

```
(CHECK widening, if a new location or mode is needed)
  → integration_provider → integration_secret     (new provider only)
  → integration_operation → integration_field
```

Filenames include `_integration_<table>`; the seed must stay **readable without
running it**:

- rows as a literal list — `op.bulk_insert(table, [_row()])`, never a variable;
- a `"code": "…"` literal in the inserted row;
- `response_root` as a string literal or a module constant, never a parameter;
- the insert's table argument resolvable — `op.bulk_insert(_table_helper(), …)` or a
  variable bound to it. Measured: an unresolved spelling made a seeded operation
  invisible to every gate, so nothing demanded its request file or its fixture.

Static readers use the newest seed per operation, and they read only `upgrade()`.
A `downgrade` that restores an older row is invisible to them by design.

### 4. Make both write paths agree

The tables have two writers — migrations, and `POST/PUT /integration/`. A
migration skips the Pydantic literal and the service validation, so **a seeded
shape the API refuses is a configuration nobody can author or edit**. Whenever a
capability is added, all three layers move together:

| Layer | File |
|---|---|
| DB `CHECK` | the migration + `models/integration.py` |
| write-time validation | `services/integration.py` |
| request/response schema | `schemas/integration.py` |

Two gates decide whether they agree, and both run both writers instead of reading
them:

- `test_seeded_configuration_is_creatable_through_the_api` replays the live seeds,
  rebuilds the create request those rows imply, and runs the service validation an
  API call gets. This fails the moment a seed carries a shape the API refuses.
- `api/integration.http` creates the new shape through the real endpoint, so
  `make check-api-flow` proves it against the running stack.

### 5. Confirm the gate noticed

Before writing anything else, ask the hooks what they see. A seeded operation the
readers cannot find is worse than an unseeded one: every later gate passes.

```bash
node --input-type=module -e 'import { listIntegrationOperations } from "./.omp/hooks/lib/backend-migration-policy.ts"; console.log(listIntegrationOperations())'
node .omp/hooks/post/check-backend-api-http.ts                     # must demand the .http file
node .omp/hooks/post/check-backend-integration-configuration.ts    # must demand the fixture
```

The new code must appear with its `root` and `configured: true`, and both hooks must
**fail** naming the artifacts that do not exist yet. Silence here means the seed is
invisible, not that the work is done.

### 6. Write the request file

`api/integration.<operation-code>.http` — one file per operation, numbered
sections whose titles state the expected status, and no state left behind:

- a **200 block per CALLER input, sending that input alone**; a call that mixes
  filters proves nothing about any single one;
- paging blocks that show the window **moving** and its **size**, plus a 422
  block that omits the family;
- the failure paths this provider actually has: an empty result, a refused
  envelope code, a missing provider (404);
- values that really return rows — verify each one with `curl` first.

### 7. Record the contract, do not write a test

Write `backend/tests/core/fixtures/integration/<operation-code>.json` — one
measured exchange, copying the shape of a sibling fixture:

```json
{
  "why": "one sentence: what this exchange proves",
  "secrets": { "service-key": "issued-key" },
  "inputs": { "range_start": 1, "range_end": 3, "…": "…" },
  "response": { "status": 200, "json": { "…": "the recorded body" } },
  "expect": {
    "path": "/the/rendered/path",
    "query": {},
    "status_code": 200,
    "canonical_payload": [{ "…": "…" }],
    "metadata": { "…": "…" }
  }
}
```

- The parametrized `test_execute_renders_the_seeded_contract` builds the client
  from the **replayed seeds**, so the fixture must never restate the field list —
  the hook rejects a fixture that does, and rejects a hand-written
  `test_execute_renders_<operation>_contract`.
- Record the refusals the provider actually has in
  `<operation-code>.<variant>.json` with `expect.raises` instead of a payload.
- Derive `expect` by running the test once and reading what it reports; a guessed
  path passes nothing (the seeds map more keys than a hand-written test ever did —
  measured: 17, 18 and 19 response keys where the old tests asserted 2).
- The seed test asserts the row counts, descriptions and pointer shapes; the
  paging standard test covers the family; write-time validation gets its own
  service test, including the shapes that must stay refused.

### 8. Gate and probe

```bash
cd backend && make lint && make typecheck && make test   # 100% coverage
cd .. && make verify                                     # every hook
make check-api-flow                                      # run every .http twice
```

Then inject the violations and confirm each one fails. A guard nobody has seen fire is
a guard nobody has. Measured on I2510 and extended on I2570, five of six fire:

| Injected | Caught by |
|---|---|
| paging inputs with no page root | `check-backend-api-http` |
| `response_root` pinning an index | `check-backend-api-http` |
| half a paging family | `check-backend-api-http` |
| a seeded shape the API refuses | `test_seeded_configuration_is_creatable_through_the_api` |
| a `CALLER` filter keyed on the wire name (`chng_dt` for `CHNG_DT`) | `check-backend-integration-configuration` |
| **a filter modelled as `QUERY` instead of `PATH_QUERY`** | **nothing** |

The last one has no gate, and it is worth knowing why: the provider accepts the
parameter, ignores it, and answers 200 with the unfiltered page. Every static reader
agrees with the configuration, and the runtime gate compares declared statuses, which
still match. **Only step 1 sees it** — one filtered call against one unfiltered call,
comparing the totals. Skipping the measurement makes this defect unreachable by any
later check.

## Discovery Pitfalls

Readers that assumed a single integration, each measured after a second provider
landed. Check these when a new provider joins:

- a provider replace cascades **its own** operations, and only from `upgrade()` —
  reading `.delete()` anywhere in a file makes a new provider's seed erase the
  first provider's operations;
- "the newest seed" is per owner, not per table — otherwise the newer
  integration hides the older one;
- insert discovery must skip `downgrade()`, or it reports the previous
  revision's `response_root` as current;
- a positional seed tuple may carry a location column, so `value_source` is not
  always the third element;
- an insert names its table three ways — inline `table("t")`, a bound variable, and a
  direct `_table_helper()` call — and knowing two of them hid the third integration;
- a helper's body must not be read across the next `def`: an unbounded scan bound the
  preceding `_id()` helper to the following helper's table, so nothing resolved.

## Never Do These

- Design from the provider's documentation alone — the docs said the filters
  were parameters, and the wire said otherwise.
- Model a path-carried query string as `QUERY`; it is accepted and ignored.
- Leave a provider that answers HTTP 200 for failures without `ENVELOPE` rows —
  an invalid key then reads as an empty page.
- Give a paging input a default, or declare half a family.
- Seed a shape the API cannot create, or add a capability without a block in
  `api/integration.http` that exercises it.
- Put a `required` row on a column the provider leaves empty for sparse records.
- Claim a window works without two calls that show it moving.
