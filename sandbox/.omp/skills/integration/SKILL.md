---
name: integration
description: Add or change a database-managed external API integration end to end - resolve the dataset name to the portal's official spec page, measure the provider, seed the configuration, prove it with a request file and a recorded contract fixture. Use when the user names a public dataset to integrate, asks to add a provider or operation, or changes an existing integration's fields, paging, or response contract.
enforced-by:
  - check-backend-integration
  - check-backend-integration-configuration
---

# External API Integration

The configuration lives in the database (`backend-integration-configuration.md`);
this skill is the order the work has to happen in, and the traps that were
measured on the way. **Measure the provider before designing anything** — every
rule below exists because a guess was wrong once.

## Workflow

### 0. Resolve the name to the official spec

The user names a dataset, not a service code. Before any call, find the portal's
own page for it and read the contract there - the code, the path, the envelope,
the columns with their meanings. A probe confirms a shape; it cannot tell you
what a column *means* (`RAWMTRL_ORDNO` was guessed as "ordinal" and the page
says 원재료표시순서 - right by luck). Two portals, two procedures, both measured
without a login:

**공공데이터포털 (`data.go.kr`) - name search, then an inline Swagger.**

1. Search by name, APIs only:
   `https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=<명칭>&dType=API`
   ("식품의약품안전처 식품영양성분DB" answered one hit, `/data/15127578/openapi.do`).
2. Open `/data/<id>/openapi.do`. The page embeds the whole Swagger 2.0 document in
   an inline script - `const swaggerJson = \`{...}\`` - so read it with the browser
   and `JSON.parse` the template literal. It carries `host` (`apis.data.go.kr/1471000/
   FoodNtrCpntDbInfo02`), the operation path (`/getFoodNtrCpntDbInq02`), and the
   response schema down to every record column with a Korean description
   (193 on that dataset), plus the paging envelope (`body.pageNo/numOfRows/
   totalCount`, `header.resultCode/resultMsg`).
3. What the Swagger does **not** carry: `parameters` is empty on these gateway
   specs. `serviceKey`, `pageNo`, `numOfRows` and the search filters come from the
   linked 참고문서 (`출력메세지_*.xlsx`) or from the probe. Error codes are the
   portal-wide "오픈API 에러코드 안내", not per operation.

**식품안전나라 (`openapi.foodsafetykorea.go.kr`) - no search; the page is keyed by
service code.**

1. Find the code: `web_search` for `식품안전나라 OpenAPI <명칭>` returns the page
   `openApiInfo.do?...&svc_no=<CODE>` whose title is the dataset's official name -
   that title match is the confirmation, not memory (`C002` = 식품(첨가물)품목제조
   보고(원재료) was confirmed this way).
2. Read the page in the browser (`document.body.innerText`; no login). It carries
   the URL shape (`/api/keyId/serviceId/dataType/startIdx/endIdx`, filters as a
   trailing path segment `변수명=값&변수명=값2`), the 요청인자 table (required
   five plus optional filters) and the 출력항목 table - column, meaning, and
   value legend (`ETQTY_XPORT_PRDLST_YN`: N 내수, O 겸용).
3. What the page does **not** carry: the envelope verdict codes (a normal page has
   no `RESULT`), and whether a filter filters. Both are step 1.

Then cross the page against one measured record, column by column, and paste the
table into the seed docstring: 10 documented, 10 measured, none missing, none
extra - or the difference, which is a finding. A page that cannot be read (login,
JS-only) is written down as such, and the seed then carries only what the probe
measured, with the column meanings marked unknown rather than guessed.

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
| How does it page? | page number + size (`PAGE`), row interval (`RANGE`), a **file** (`CSV`, step 1a), or not at all |
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

### 1a. Divide the feed by the quota before choosing the door

A whole pass is `total_count / page_size` calls, and a key has a daily ceiling.
Do that division before seeding, because a feed that does not fit one night is
not a feed the paged door can carry - measured on I0460: 2,047 windows against
~500 calls a key a day (`INFO-300` after 498/496/497 on three keys), the job
dying at 73 % with the ledger untouched. Neither the hourly `INFO-320` nor the
7-day `LAST_UPDT_DTM` increment changes that arithmetic.

When it does not fit, **look for the portal's bulk file before anything else.**
식품안전나라 states it in its own INFO-000 message ("전체 데이터를 원하시는 경우
CSV 다운로드 기능을 이용해 주십시오"), prices it separately (`INFO-330`, ten a
day a key and a service), and the door is a path, not a `data_type`:

```bash
curl -sS -o feed.csv.gz -w '%{http_code} %{content_type} %{size_download}\n' \
  "http://openapi.foodsafetykorea.go.kr/api/KEY/SERVICE/file"
```

Measure the four things the file shape rests on, and paste them into the seed:

| Question | What decided on I0460 |
|---|---|
| Is it exact? | the recorded API window's rows found in the file, column for column, to the microsecond |
| How many rows, and do they equal `total_count`? | 2,046,504 = the API's total (a naive line split over-counts by ~450 quoted newlines) |
| How does it refuse? | **HTTP 429** with an XML body: `INFO-500` busy key (~40 s), `INFO-330` the day's ten - a status, not an envelope |
| Is its quota the API's? | no: the file answered while the same key was `INFO-300` on the API; open inside the 09-19 KST silence too |

Then seed `response_format = 'CSV'` (rule://backend-integration-configuration,
"A File Is a Transport"): REQUEST is the key and the service, no root, no
envelope, no paging inputs, the **same RESPONSE rows** (`/COLUMN` pointers),
retries wide enough for the busy key, and `quota_codes` empty. The fixture
records the gzip bytes and the rows the reader made of them. Nothing above the
walk changes: the job, the stage and the derivation read a file exactly as
they read a page.

### 1b. A portal with no API: measure the screen, not the page

Check that "no API" is true first - it was not, for the first screen this was
built for (수입식품, step 8b below). The screen transport in the codebase has no
seeded operation using it today and is kept for the portal that really has none.

Some datasets are a public **screen** and nothing else (수입식품정보마루,
`impfood.mfds.go.kr`). The probe target does not fit; the browser does.
The transport is one column (`integration_provider.transport = HTML_FORM`), so what
this step produces is the same seed as an API - with these measurements in it:

1. **Capture the browser's own request.** Open the screen in the harness browser,
   register `page.on("request")` for the list URL, click search with a real click,
   and dump `method`, `headers` and `postData()`. That body is the form field set -
   **exactly** those parts, in that order. Measured: the screen's HTML holds 18
   inputs and its JS posts 15; posting the 18 answered `302 -> /error/error`, the
   15 answered 200. Scraping the `<form>` is the wrong measurement.
2. **Replay it from `httpx`, not the browser.** GET the screen (the cookie), then
   POST the captured parts as `files={name: (None, value)}` with `Referer` set to the
   screen. If that answers the table, no browser is needed in the batch. Then
   strip headers one at a time: `Referer` alone was enough here, `Origin` was not
   needed, `User-Agent` was not read.
3. **Find the empty state and the end.** Post an empty form, and a page past the
   last one. Both drew the table with one placeholder row (`조회 결과가 없습니다`,
   `colspan=10`) - a row the row selector must exclude (`tr:has(a)`), or the walk
   stages it as a record. This is the second fixture the gate demands.
4. **Find the identity.** Nothing on the row was unique; the detail link was
   (`a@href` -> `fnFoodDetail('202600642199')`). Read the attribute with a
   `selector@attribute` locator and let the ledger take the number out.
5. **Find where the total is printed, and on which pages.** `총 N건` sat in
   `<strong>` inside a `<span>`, so a regex over raw HTML misses it and a `REGEX`
   locator over the document text finds it; and it was printed on page 1 only
   (`총 0건` from page 2, the screen echoing the empty `totalCnt` it was sent).
   Nothing walks on it either way.
6. **Widen the window and page to the end before designing a family.** The
   screen's default 3-month window is its JS, not the server: `1990-01-01 ~
   2099-12-31` answered every row (1,088,839), and `page` reached 1089 at limit <!-- history-ok: probe parameter -->
   1,000. A "date window" paging family was designed here and measured
   unnecessary - two LITERAL rows and `PAGE`. Measure the width too: 100 through
   10,000 all answered, and every call took 16-27 s whatever the width.

**Measure the host's rate before the first walk, and measure it by ramping.** A
screen has no quota code to read: it simply stops answering. Ramp one connection -
40 calls a second apart, 60 half a second apart, 80 a quarter apart - and stop at
the first failure. Measured on impfood: the first two stages were
answered in ~100 ms each and the third died after 38 calls, taking **every**
connection to the host with it for about fifteen minutes - the nightly list job's
included. Seed the answer as `integration_provider.min_interval_ms`; the client
paces every call of a pass with it, so no job can forget it.

**Check the layout a non-browser is served.** The same screen answered
`python-httpx` with mobile markup where two columns share a cell, and a Chrome
agent with the desktop one. Fetch it both ways and diff the byte count before
seeding a selector; then seed a `User-Agent` LITERAL header and name the layout's
own class in the selector, so the wrong layout reads nothing instead of reading two
values as one.

Seed it as `response_format = HTML`, `response_root` = the row selector,
`request_media_type` = what the browser sent, `request_schema` closing the part set
(`"required": FORM_FIELDS`, `"additionalProperties": False`), and every RESPONSE row
with a `locator_kind` (`CSS` / `LABEL` / `REGEX`). The rule's "A Screen Is a
Transport" section is the contract; `check-backend-integration-configuration` refuses
a form seed that does not close the set, a screen fixture without `expect.form` and
`expect.bootstrap_path`, and a screen operation without its `<code>.empty.json`.

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
- A screen's response is `"text"` instead of `"json"`, trimmed to the nodes the
  locators read (the total's span and the table with two rows - 3 KB of a 643 KB
  screen), with `expect.form` and `expect.bootstrap_path`; and a second file
  `<operation-code>.empty.json` records the page past the last one with
  `canonical_payload: []`.
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
| a file operation with a root, an envelope row or a paging input | `check-backend-integration-configuration` (`checkFileOperations`) |
| a file operation whose fixture records JSON instead of the gzip bytes and the rows | `check-backend-integration-configuration` |
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

### 8b. Before seeding a screen, look for its bulk publication

A portal screen and a data.go.kr dataset are often the same records. Measured:
수입식품조회 (1,088,673 rows over 109 window calls) is the same
population as `IprtFoodPrdtKoreanLabelingText` (1,087,781 rows, 2,176 calls of 500,
66 minutes) - and the API also carries the printed 한글표시사항 the *detail* screen
would have cost 25 days to crawl. Search the portal by dataset name and compare
totals and a year histogram before writing a screen seed; the login and the
활용신청 are one click each, and the account's key is what the seed then carries.

**Standing decision:** the 수입식품 screen feed (수입식품정보마루) was seeded,
walked whole, and retired for exactly this reason - the API ledger is the
source of record for 수입식품, and the screen transport survives with no
operation using it (rule://backend-integration-configuration, "A Screen Is a
Transport").

### 9. A paging operation is not done here

`make verify` stays red after step 8 when the operation pages: `check-backend-batch`
asks for the `Feed` that walks every seeded paging operation, and names the job it
belongs in (`sync_<provider>_ledgers.py`). That is the hand-off, not a false
positive - an integration target is a ledger (`backend-ledger.md`), and the seed is
the first half of it. Continue with the `ledger` skill in the same change: the
table, its `replace_<table>_ledger`, the `Feed`, and the numbers from a live pass.
A lookup operation (no `range_start`/`page_no` among its caller inputs) ends at
step 8.

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
- Name a service code or a column's meaning from memory. The code comes from the
  portal page whose title is the dataset's name; the meaning from its 출력항목
  table or the Swagger description. A probe proves a shape, not a name.
- Model a path-carried query string as `QUERY`; it is accepted and ignored.
- Leave a provider that answers HTTP 200 for failures without `ENVELOPE` rows —
  an invalid key then reads as an empty page.
- Give a paging input a default, or declare half a family.
- Seed a paged operation for a feed whose windows exceed a day of the key
  pool's quota. Divide first (step 1a); the file door, when the portal has one,
  is the only door that carries such a feed.
- Seed a shape the API cannot create, or add a capability without a block in
  `api/integration.http` that exercises it.
- Put a `required` row on a column the provider leaves empty for sparse records.
- Claim a window works without two calls that show it moving.
- Seed a screen's form from its HTML. The form is what the browser **posts**;
  three inputs the JS never sends turned a 200 into a 302.
- Design a paging family from a screen's default filter. Widen the filter to
  everything first; the family is what remains after that.
- Stop at the seed for an operation that pages. Two operations sat seeded and
  unread for the life of five sync jobs because the gate asked only whether what
  a job named existed, never whether what existed was walked.
