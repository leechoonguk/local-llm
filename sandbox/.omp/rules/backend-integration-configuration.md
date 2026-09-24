---
description: Database-managed IntegrationClient configuration — provider, named secrets, operations, unified wire fields
globs:
      - backend/app/models/integration/*.py
      - backend/app/schemas/integration/*.py
      - backend/app/repositories/integration/*.py
      - backend/app/services/integration/*.py
      - backend/app/routers/integration.py
      - backend/app/core/integration.py
      - backend/app/core/settings.py
      - backend/alembic/versions/*_integration_*.py
      - backend/tests/api/test_integration.py
      - backend/tests/core/test_integration.py
      - backend/tests/services/integration/*.py
alwaysApply: false
---

# Backend Integration Configuration

## Overview

External HTTP configuration is stored in four tables and executed only through
`IntegrationClient`. Configuration is updated outside active calls; therefore
there is no configuration revision, configuration cache, or invalidation path.

## A Seeded Operation States Its Window

`integration_operation.page_size` has a `server_default` of 100, so a seed that
does not name it is 100 - silently, and only the clock says so. Measured:
eleven 식품안전나라 operations were seeded that way when the width moved
from the job to the operation, and the walks that had read 1,000 rows a
window went on reading 100 - a tenfold pass, hours instead of minutes,
per-window latency climbing as the offset grew, and ten times the calls
spending quota refusals that locked the whole key pool (numbers:
`decks/ledger-measurements` §10). A corrective revision set the eleven to
1,000 (the portal's own ceiling - a wider window answers `INFO-320`).

Every seed written from revision 270 on states `page_size` explicitly;
`check-backend-integration-configuration` refuses one that does not. The current
widths per provider are in `decks/ledger-measurements` §10.

## A Service Says How Its Feed Is Addressed

`segment_key` and `segment_values` are the same kind of fact as the width:
which caller input a service publishes one set per (`report_year` on 생산실적), and
the values that input takes. A `CHECK` stores them together or not at all — a key
with no values has nothing to ask for, values with no key have nothing to be put
in — and a second `CHECK` refuses an empty list.

**The values are listed, never derived.** Code that generated candidates would
have to know what the coordinate is; listing them leaves the walk ignorant of
whether a 보고년도 counts upward or a region code does not. Listing ahead of the
portal is free: an unpublished value answers zero rows to a one-row probe and is
skipped, so the next year is already on the row before it opens.

**They are seeded by a migration and by nothing else.** The pair is absent from
`IntegrationOperationCreateRequest` — present on the read response so an operator
can see it, refused on the way in by `extra="forbid"` — because the coordinate is
not an operational knob. It does not select data: a ledger is the **whole feed,
walked from the first window and replaced entire**; the coordinate only decides
how that one pass is addressed. A row edited between passes would change the
cost of a walk, never its result, and a configuration that can only be changed by
revision is one every environment shares.

They are configuration and not job constants for the same reason the width is:
the walk that reads them is shared by every provider job, and a coordinate is
knowledge only the service has. The cost is not cosmetic — a feed read flat
costs the square of its windows, ~48 h against ~6 h on I0300 (rule://backend-ledger,
`decks/ledger-measurements` §13).

## Data Model

- `integration_provider` owns `code`, HTTPS `base_url`, display name, and enablement.
  **A provider is a portal, never a dataset**: one host and one credential, with an
  operation per dataset under it. The seeded row read
  `공공데이터포털 식품영양성분DB` / `data-go-kr-food-nutrition`, which named a
  dataset in the provider — and a dataset in the provider leaves the portal's second
  dataset nowhere to go but a duplicate provider row holding a second copy of the
  same `service-key`. It is now `공공데이터포털` / `data-go-kr`, and the dataset is
  what its endpoint already says: `search-food-nutrition` on
  `/1471000/FoodNtrCpntDbInfo02/…`. The sibling portal is the shape that works —
  `mfds-food-safety-korea` carries four operations under one key.
  `check-backend-migrations` reads this **by host**, because the name is the thing
  that drifted: two provider seeds resolving to one `base_url` host are refused.
- `integration_secret` owns one **named** credential per provider (`(provider_id, name)`
  unique). A field references it by FK, so a key is rotated in one place, survives a
  full replacement of an operation's fields, and is stored once no matter how many
  operations send it. Read responses expose the name, never the value.
  **A pool is a property of the secret.** Secrets of one provider sharing a
  `rotation_group` are interchangeable, and the caller sees one credential. The group
  lives on the secret and not on the field or the operation because the keys are the
  portal's and so is their quota: six operations under `mfds-food-safety-korea` would
  otherwise each carry a list of the same three keys, and the list that missed the
  fourth key would be the one running that night. `exhausted_until` is the only runtime
  state on the table - when a member answered one of the operation's quota codes, plus
  that code's sit-out. Written by a Core UPDATE without the version
  bump: the job and the endpoint that hit the quota in the same second must both
  succeed, and no reader compares this column's revision.
- `integration_operation` owns method, relative path template, timeout/retry policy,
  idempotency, request JSON Schema, `response_format` (JSON|XML), `response_root` —
  the whole response contract — and `quota_codes`: the envelope values that mean "not
  this key right now" rather than "this answer is wrong", each with the seconds the key
  sits out (`{"INFO-320": 3600, "INFO-500": 60}` on the mfds portal: the hour's quota
  recovers within the hour, a "busy key" within seconds - an hour for a moment would
  shrink a three-key pool to one). Disjoint from the ENVELOPE row's accepted values by
  construction (`_validate_quota_codes`): a code that is "success" and "spent" at once
  would never turn the pool. **Mapping is the only response contract**: the RESPONSE
  rows always build the canonical payload. `response_root` says what they are resolved
  against: absent, one record through absolute pointers; present, every element of the
  page it names through element-relative pointers.
- `integration_field` is one row per wire field, inbound or outbound, discriminated by
  `direction`, and `location` says how it travels:
  - `REQUEST` — `key` is the caller-facing input name, `wire_path` the wire name/pointer,
    and `value_source` (`CALLER`|`LITERAL`|`SECRET`|`CONTEXT`) says where the value comes
    from. `value` holds the literal (LITERAL) or the reference (SECRET, through
    `secret_id`). **A `CALLER` row carries no default**: `_resolve_value` never falls
    back to `value`, and an omitted input is omitted from the request. A hidden default
    is a second source of truth that sends what nobody asked for; a `required` `CALLER`
    field that is missing is `IntegrationInputError` (422, `integration_input_invalid`) —
    the caller's fault, distinct from configuration (422) and from upstream (502).
    Exactly one source per row. A value the caller sends that cannot be rendered in the
    row's `value_type` is also 422 and names the input: `page_no="abc"` used to escape as
    a bare `ValueError` and answer 500.
  - `RESPONSE` — `key` is the canonical result key and `wire_path` the RFC 6901 pointer
    (BODY, relative to a page element when the operation names a page) or header name
    (HEADER). `value_source` is always NULL.

| `location` | Direction | What it means |
|---|---|---|
| `PATH` | REQUEST | fills a `{placeholder}` in the path template |
| `PATH_QUERY` | REQUEST | a query string the provider only reads **as a path segment**: the enabled rows are joined `k=v&k=v` and appended. Measured on I1250 — sent as a real query string the filters are accepted and silently ignored, so the location names the transport |
| `QUERY` | REQUEST | ordinary `?k=v` |
| `HEADER` | REQUEST/RESPONSE | header name; RESPONSE headers may carry `match_mode` |
| `BODY` | REQUEST/RESPONSE | JSON pointer into the body; RESPONSE BODY rows build the canonical payload |
| `ENVELOPE` | RESPONSE | absolute pointers into the body **wrapper**, checked before the page is mapped. A row with a `match_mode` is a verdict (`ONE_OF ['INFO-000','INFO-200']`); a row without one is carried into `metadata`. Measured on I1250: every outcome is HTTP 200, so an invalid key (`INFO-100`, no rows) is indistinguishable from "no data" (`INFO-200`, no rows) until the wrapper is part of the contract |

One operation belongs to one provider. Every field uses an operation UUID FK;
never duplicate provider or operation code strings across configuration tables.

### A Screen Is a Transport, Not a Second Stack

**No operation uses this transport today, and the code stays anyway.** The
first screen feed was walked whole and then retired the moment its records
were found published in bulk as an API - which dataset, and the comparison
that decided it, are the `integration` skill's record (§8b; walk timings:
`decks/ledger-measurements` §5). What is kept here is the transport and its
measurements - the HTML client, the session bootstrap, `min_interval_ms`, and
the four locator kinds - because the next portal without an API needs exactly
them.

`integration_provider.transport` says how the portal answers, and it is the only
switch: `HTTP_JSON` is an API — a credential in, a JSON or XML body back —, and
`HTML_FORM` is a public screen with no API at all. Everything else the screen needs
is already this configuration's vocabulary, so a screen is seeded like any other
provider: an operation per screen, `integration_field` rows for its form and its
cells, `quota_codes` and retries unchanged. There is no crawler domain, no second
client, and no browser in the batch — measured on impfood.mfds.go.kr: the
list answers a plain `httpx` POST.

What the screen adds is three columns:

- `integration_provider.bootstrap_path` — the screen whose GET mints the session
  cookie, fetched once per client before the first call and again exactly once when
  an answer is refused. The jar lives on the client and never in a table: a cookie
  that expires in minutes is not configuration, and a stored one is a stale row that
  fails tomorrow's run. The same helper sets `Referer` to that screen, because the
  portal reads it (measured: the POST redirects to `/error/error` without it).
- `integration_operation.response_format = 'HTML'` — the decoder. `response_root` is
  then the **row selector** (`table.board_list tbody tr`) rather than an RFC 6901
  pointer, and its empty state is the same "past the last page" a JSON provider
  states by dropping its items key.
- `integration_field.locator_kind` — how a RESPONSE row reads its value.

| `locator_kind` | Reads | Why it exists |
|---|---|---|
| `POINTER` | RFC 6901 into the decoded body | every JSON and XML row; the default, and the only kind a REQUEST row may carry |
| `CSS` | a selector inside the row (`td:nth-child(3)`) | a list screen numbers its columns and names none of them |
| `LABEL` | the `td` beside the `th` with that text | measured on `CFCCC01F03`: a record carrying 부적합/회수 blocks moves every later header, so a positional locator reads a neighbour's value |
| `SECTION` | `<heading>|<selector>` - the selector inside the block that heading introduces | a detail screen's repeating groups are tables sharing one class inside anonymous divs, so a positional selector reads a different group per record kind; the `h3` above each is the only stable anchor |
| `REGEX` | the first group in the document's text | a screen states its total in prose (`총 29,930건`), which is the only place the walk can read how far to go |

An HTML locator on a JSON operation is a configuration error (422), not a 502: the
seed cannot be read at all. A number a screen prints for people (`29,930`) is typed
at the read, thousands separator dropped, because the ENVELOPE total goes straight to
the walker and nothing downstream converts it.

`request_media_type` is the whole outbound encoding decision and now means it for
forms too: `multipart/form-data` and `application/x-www-form-urlencoded` send the
rendered BODY rows as form fields, anything else sends JSON. Measured: the same
values as a JSON body answer the error page. **A form row set is exact** — the screen
refused the request when three fields its own JS never sends were added, so a seed
mirrors the fields the screen posts, no more. The seed states that as the
operation's `request_schema` — `"required": FORM_FIELDS` and
`"additionalProperties": False` — so the client refuses a sixteenth part as a 422
before the portal's 302, and `check-backend-integration-configuration` refuses a
form operation whose schema does not close the set.

Four more facts of the first screen feed (`search-import-food`), each
of which is a gate because each was a live defect:

- **A screen draws "no rows" as a row.** Past the last page, and for an empty
  window, `table.board_list tbody tr` matches one `td colspan=10` reading 조회 결과가
  없습니다. Only real records link to their detail screen, so the row selector is
  `tr:has(a)` and the placeholder is an empty page. The check demands a second
  fixture, `<code>.empty.json`, recording that page with `canonical_payload: []` -
  without it the walk would stage the placeholder as a record and never see the end.
- **The identity is in the link.** Nothing a reader sees on the row is unique; the
  `a@href` reads `javascript:fnFoodDetail('202600642199');` and the ledger takes the
  number out (`MfdsRecord.link_number`). A `CSS` locator ending in `@attribute` reads
  that attribute instead of the text.
- **The total is printed once.** `총 N건` is the whole feed on page 1 and `총 0건`
  from page 2 on (the screen echoes the empty `totalCnt` it was sent). Nothing reads
  it to walk - the walk ends on the empty page - so it is metadata, never a bound.
- **The fixture records the form and the session.** `expect.form` is the part list the
  browser posts, asserted part for part against the multipart body the seeded rows
  render; `expect.bootstrap_path` is the screen the client fetches first. The contract
  test answers that GET itself, so a fixture proves the cookie is minted before the POST.

Two more forms a `CSS` (or `SECTION`) selector may take, each measured: `a@href`
reads an attribute, because a list screen keeps a record's identity in its link and
nowhere a reader can see; `td:nth-child(2)[]` reads **every** match, newline-joined,
because a screen repeats a value down a column (원재료 한글명, one `td` per
ingredient) and a ledger keeps a published list as the wire printed it - the split
into rows is a derived table's job.

**A screen may serve a different layout to a non-browser.** Measured on
the detail screen: `python-httpx` was answered the mobile markup
(`td.mo-td`) where 한글명 and 영문명 share one cell as `정제수 / WATER`, and a Chrome
agent the desktop one (`td.pc-td`, one value per cell). So a screen
operation seeds a `User-Agent` LITERAL header, and its selectors name the layout's
own class - served the other one they read nothing, which is a NULL and not a
silently merged value.

**A host's rate is the provider's**: `integration_provider.min_interval_ms` is the
floor on the gap between two calls, enforced by the client, which is one client per
pass. Measured on impfood: 2 calls a second were answered and 3 got **every**
connection to the host refused for ~15 minutes - the nightly list job included. It
is 0 for every API provider here, whose limit is a quota code instead.

The date window is not a paging axis. Left empty the screen fills three months by
itself; given `1990-01-01 ~ 2099-12-31` it answers the whole feed (1,088,839 rows) and <!-- history-ok: probe parameter -->
`page` walks it to the end (page 1089 at limit 1,000 answered the last 839). So the
window is two LITERAL rows and the family is `PAGE` - a `WINDOW` family was designed
and then measured unnecessary, and it is not to come back on the strength of the
screen's default.

### A File Is a Transport, Not a Faster Page

`integration_operation.response_format = 'CSV'` is a **file door**: one GET
answers the whole feed as a gzip CSV, and `IntegrationClient.stream` reads it
off the wire in chunks of `page_size` records. It exists because a feed was
measured unwalkable by page: 식품안전나라 I0460 is 2,047 windows against a daily
ceiling of ~500 calls a key (three keys reached 498/496/497 successful calls
and answered `INFO-300`; the job died at window 1,495 with the ledger,
correctly, untouched), while the portal's own `/api/{key}/I0460/file` answered
the same 2,046,504 rows in four seconds on a quota of its own - ten downloads
a day, a key and a service (measurements: `decks/ledger-measurements` §14).
The paged operation was replaced by the file (revisions 286/287); nothing
above the walk changed.

What a file operation is, and is not:

| Shape | Paged operation | File operation |
|---|---|---|
| REQUEST rows | key, service, window, filters | key and service, nothing else - the door takes no window and no filter |
| `response_root` | the page | NULL: the file is the page |
| ENVELOPE rows | the wrapper's verdict | none: success has no wrapper, and a refusal is an **HTTP 429** whose XML body the call log keeps (`INFO-500` busy key, ~40 s; `INFO-330` the day's ten) |
| RESPONSE rows | element-relative pointers | the **same rows**: a one-segment pointer (`/PRDTNM`) reads the column of that name |
| `page_size` | rows a window asks for | rows a chunk hands the stage - the step log reads the same intervals |
| `quota_codes` | envelope values | empty: nothing arrives in an envelope |
| retries | 200 ms | wide enough to wait out a busy key: 15 s, 30 s, 60 s |
| `execute()` | one window | the **download** - name, type, bytes, rows in `metadata`, an empty page - because two million rows are not an answer to the endpoint an operator presses |
| walk | windows until a short page | `stream` (through the walk's `_stream_operation`): inflated and decoded as it arrives, cut at RFC 4180 record boundaries (450 quoted newlines in that file), a page per `page_size` records, every step pointing at no call because the one call ends after the last step |

Measured facts the shape rests on: the file is exact - the recorded API window's
rows are in it column for column, to the microsecond; a naive line split loses
~450 rows to quoted newlines, so the reader cuts at balanced quotes; `/I0460/csv`
as a `data_type` is `ERROR-301`, the file is a path of its own.

Write-time (`_validate_file`) and the hook (`checkFileOperations`) refuse the
three shapes that cannot apply - a root, an envelope row, a paging input - and
the hook demands a fixture that records the **gzip bytes** and the rows the
reader made of them (`response.gzip_base64`, `expect.rows`): the reader is what
a file adds, and a JSON fixture proves none of it.

**A segmented feed loses its coordinate at the door.** `segment_key` is how a
paged walk reaches one year at a time; a file answers every year at once, so
converting an operation sets `segment_key` and `segment_values` to NULL. Left
in place, the pass downloads the whole file once per segment - ten of the ten
downloads a key gets in a day, for one pass.

**The wire is drained before a record is cut.** A consumer that stages every
`page_size` records into Postgres pauses between reads, and the portal's Apache
closes a connection that idles: measured, 축산물 생산실적 (41.8 MB, 3.4 M
records) died 126 s in under the job while `execute` - which reads as fast as
it can - took the same file whole in 42 s. `stream` writes the body to a
`SpooledTemporaryFile` at wire speed and cuts records from it afterwards, so a
pass does not depend on how slow its consumer is.

**A body that stops halfway carries no status.**
`ck_integration_call_answered` lets an unanswered call hold none, so a
mid-stream transport error records `UNREACHABLE` with no status code. Recording
the 200 that opened the body made Postgres refuse the log row and failed the
pass for its logging rather than for its feed.

### Paging Is an Endpoint Setting, and Its Shape Is Fixed

An operation either **pages** or it **does not** — there is no third state. Paging
is declared per operation, by its **REQUEST field configuration**, never by
client-side convention. The canonical `key` is ours and standardised; the
`wire_path` stays whatever the provider calls it:

| Family | Canonical keys | Meaning | Wire example |
|---|---|---|---|
| `PAGE` | `page_no` + `num_of_rows` | which page, and how many rows in it | `pageNo`/`numOfRows` |
| `RANGE` | `range_start` + `range_end` | which row interval | `startIdx`/`endIdx` |

**A family is added by the first live operation that needs it**, together with its wire
mapping and its `.http` proof — never before. `RANGE` was written here once for an
operation a provider replace had already deleted, and deleted again for that reason; it
is back because I1250 (식품(첨가물)품목제조보고) pages by row index and has no page
number at all. A standard with no caller cannot be wrong out loud, and every reader
still has to implement it.

An operation declares **one whole family, or none of it**:

- half a family is not a window, and two families at once is not a window either — a
  position without a size (or the reverse) fails the gate, in the service and in the
  hook;
- every paging field is `CALLER`, `required`, **and carries no `value`** — a
  default in the row sends a window nobody asked for, and falling through to the
  provider's default leaves the window unstated. A missing paging input is
  `IntegrationInputError` (422), not a quietly different page;
- a paging operation **names the page**: `response_root` is required, and it must not
  pin an index. `/body/items/0` returned one record however large the page was, which
  made the page-size input unobservable (measured). The RESPONSE rows are then
  resolved against each element, so one row per provider column describes every record
  the window carries — the caller gets the whole page, and every column keeps its key,
  type and description.

**This is the pattern for every paging integration, and it is the only one.** There is
no mode to choose: mapping builds the payload, and `response_root` is the difference
between one record and a page. A provider that pages therefore always looks the same
here — paging inputs `CALLER` + `required` + no default, a root at the page, rows
relative to an element — which is what makes a second paging provider a configuration
exercise instead of a design discussion.

Enforcement is split by what each side can see, and both sides check the seed:

- **configuration** — `test_paging_standard_holds_for_every_operation` replays the
  seeds and reads `value_source`, `required`, `value` and `response_root` from the
  rows, which a regex cannot do honestly;
- **repository** — `check-backend-api-http` reads the newest operation seed: paging
  inputs with no `response_root`, or a root that pins an index, fail there before any
  database is involved;
- **write time** — `IntegrationProviderService._validate_response_root` refuses the same two
  shapes through the API, so the configuration the app serves is one the app can
  create;
- **request file** — a 200 block per canonical paging key (the window moves, and its
  size is observable) plus a **422 block that omits both**, because "required with no
  default" is a claim until a call proves it is refused. An operation that seeds no
  paging must not send paging inputs either — an input no field row declares is
  dropped in silence.

### A Seed the Database Does Not Have

`integration_operation.provider_id` is **ON DELETE CASCADE**, so a provider
`_replace_` (delete + insert) takes every operation seeded before it. Revisions
16/17/18 seeded `search-domestic-food-products`; the provider replace at revision
20 erased it, and nothing re-seeded it. Measured today: the API lists one provider
with one operation, and the execute endpoint answers that code exactly like a code
that never existed.

It is **closed, not pending**: reviving it means a new revision pair (operation,
then fields) with the provider and credential it actually needs — its path
(`/api/{service_key}/I1250/json/{start}/{end}/…`) belongs to
`openapi.foodsafetykorea.go.kr`, not to the seeded `apis.data.go.kr` provider.
Until then the discovery in `lib/backend-migration-policy.ts` and
`test_every_seeded_operation_owns_a_request_file` both honour the cascade, so no
gate demands a request file, a contract-test anchor or a paging contract for a row
no database has.

**Static readers cannot see this on their own.** Hooks read migrations,
hermetically — which is why the declared operation set is compared against the
live API in `make check-api-flow` (`checkSeededOperations`). A cascade the parser
does not model, a migration that never ran, or configuration created by hand shows
up there as a difference between what the repository claims and what the database
serves.


### Why this shape

The previous five-table shape failed in four ways this design fixes:

| Defect | Consequence | Fix |
|---|---|---|
| `operation.response_schema` duplicated the response field rows | the two drifted; a nullable-type omission turned a valid provider response into a 502 | `response_schema` removed — `required` RESPONSE rows are the response contract |
| secrets lived on the field row (`secret_ref`/`secret_value`) | replacing an operation's fields destroyed the key (twice), and one key was stored per row | `integration_secret` + `secret_id` FK |
| five sparse exclusive columns under one large CHECK | every new source rewrote the CHECK | `value` (JSON) + `secret_id`, one small CHECK per rule |
| a mapped response needed absolute pointers, so a second `PASSTHROUGH` mode existed to return pages | a paged answer could either be mapped or be whole, never both — and passthrough columns had no key, type or description anywhere | rows resolved against each page element: one pattern, `response_root` is the only decision, and the mode column is gone |

### Two Writers, One Definition of Valid

The four tables have two writers: alembic seeds, and `POST/PUT /integration/`. A
migration reaches them through the DB `CHECK` alone — it never meets the Pydantic
literals or `IntegrationProviderService`'s validation. So the same invariant is written three
times, and a capability added to two of them leaves the third refusing rows the
database already serves.

**A seeded shape the API refuses is a configuration nobody can author or edit.** An
operator who reads a provider back and submits one changed timeout is refused over a
row they never touched, and the service's rule becomes prose that guards nothing.

Measured three times on the same axis, each after the DB and the runtime learned a
shape the validator did not: `MAPPED` with a page root, a `match_mode` on an
`ENVELOPE` row, and — in the other direction — paging with no root, which the API
allowed while the standard forbade it.

`test_seeded_configuration_is_creatable_through_the_api` closes this by **running both
writers**: it replays the live seeds, rebuilds the create request that would produce
exactly those rows, and hands it to the validation an API call gets. Reading the
validator with a fourth reader is how the first two divergences survived. When a
capability is added, move all three layers and let this test decide:

| Layer | File |
|---|---|
| DB `CHECK` | the migration + `models/integration/*.py` |
| write-time validation | `services/integration.py` |
| request/response schema | `schemas/integration/*.py` |

## Runtime Contract

- Create clients with `IntegrationClient.from_database()` and run `execute()`.
  Do not restore raw `headers=`, caller-supplied URL, or `response_model=` APIs.
- `IntegrationExecutionResult` returns only canonical payload, approved metadata,
  and status code. Provider-specific response field names do not leak into services.
- `X-Request-ID`, 2xx success semantics, idempotent retry, exponential backoff,
  and standard `Retry-After` handling remain transport behavior in code.
- Validate request bodies with JSON Schema 2020-12. Reject external `$ref`,
  scripts, templates, and dynamic evaluators.
- **RESPONSE rows always validate, and always build the payload.** A `required` row
  whose pointer does not resolve is an `IntegrationError` (502). `response_root` is the
  only decision, and it has exactly two shapes:

  | `response_root` | `wire_path` | Canonical payload |
  |---|---|---|
  | absent | absolute pointer | one object built from the rows |
  | a pointer at a page (array) | **relative to one element** | array of mapped objects, one per record |

  A root that pins an index (`/body/items/0`) truncated every paged answer to its
  first row and made a page-size input unobservable (measured), so it is refused at
  write time and in the repository. An **absent** node at a declared root is an empty
  page, not a failure: past its last page this provider answers `resultCode 00` with
  `totalCount` intact and no collection key at all, so calling that a 502 blames the
  provider for saying "no rows". A root that resolves to a **record or a scalar** is a
  502 naming that: the rows are written relative to an element, so mapping a single
  object would hand back one record for a paged call.
- `SECRET` fields resolve through `integration_secret.value` at call time; a disabled
  or missing secret is an `IntegrationConfigurationError` (422). Never use environment
  variables for integration secrets, and never echo a secret value in a read response.
- **The key pool is invisible above the operation service.** `execute_operation` lists
  the provider's grouped, enabled, unspent secrets, picks a member per group by a
  per-process round-robin (random start, advancing per call - no row write per call,
  so the scheduler and a manual run spread across the pool without a lock), and hands
  the choice to `IntegrationClient.from_database(secrets=...)`. An answer carrying one
  of the operation's `quota_codes` sits that member out for the code's seconds and
  sends the same request with the next one; every try is its own `integration_call` row carrying
  `secret_name` (the name, never the value). The caller sees the provider's refusal
  only when every member is spent - the batch job's "leave the cursor and stop" is
  then the right ending, and it did not change. `batch/`, `routers/` and
  `dependencies/` may not mention `rotation_group`, `exhausted_until`, `list_pool` or
  `mark_exhausted` (machine-checked): a caller that re-implements the rotation once
  is the copy that forgets to mark the spent key.

## Request and Response Rules

- Header names are case-insensitive. `host`, `content-length`, `transfer-encoding`,
  `connection`, `upgrade`, `proxy-authorization`, `te`, and `trailer` are forbidden.
- `authorization`, `cookie`, `x-api-key`, and names containing token/secret/key/
  credential require `value_source="SECRET"` and `sensitive=true`.
- BODY field paths and response mappings use RFC 6901 JSON Pointers. `ENVELOPE` rows use
  absolute pointers into the wrapper, never element-relative ones — the wrapper is not
  part of the page.
- Value matching modes are `IGNORE`, `PRESENT`, `EXACT`, and `ONE_OF`. They apply to
  RESPONSE rows in two locations — `HEADER` and `ENVELOPE` — because both carry a value
  the provider chose. A REQUEST row or a mapped `BODY` row with a mode is a claim
  nothing enforces, and is refused at write time and by a CHECK. `EXACT` takes exactly
  one expected value, `ONE_OF` at least one, and `IGNORE`/`PRESENT` none.
- Response field keys are lower snake case, derived from the field's description
  (see External API Spec Fidelity). Only type conversion is allowed; arbitrary
  transformations are forbidden.
- `EPOCH_SECONDS`, `HTTP_DATE`, and `DURATION_SECONDS` are header-only value types.

## External API Spec Fidelity

Configuration mirrors the provider's published spec, not a hand-picked subset:

- **Every** request parameter in the spec gets a `REQUEST` `integration_field`
  row. Omitting optional parameters silently removes capability from callers.
- `required` reflects the **provider's** contract, not our convenience: mark
  `required=true` only for parameters the API rejects the call without (usually
  just the auth key). Parameters with provider-side defaults (`pageNo`,
  `numOfRows`, `type`) and search filters are `required=false`.
- Every column the caller may read gets its own `RESPONSE` row carrying `key`,
  `wire_path`, `value_type` and `description`. With a page root those rows are
  element-relative, so **one row per column describes every record on the page**: a
  193-column provider is 193 rows, and the field dictionary lives in the database
  instead of a spreadsheet. The cost is honest — those rows move when the provider's
  spec moves — and the alternative was measured: returning the provider's node
  verbatim cost one pointer and gave the caller columns with no name, type or
  description anywhere in the system.
- `description` is mandatory on every field row — it carries the provider's own
  wording (with its sample value where given) so operators read the contract from
  the database, not the vendor PDF. When the provider publishes a response field
  sheet, these rows are how that document stops being the only copy.
- **The canonical key comes from the field's description, not from the wire name.**
  157 of this provider's columns are `AMT_NUM<n>`, which names nothing: a caller
  reading `amt_num13` learns less than the provider's own sheet already says, and the
  mapping becomes invisible — the response looks like a passthrough with lowercase
  keys. `AMT_NUM13`/`나트륨(mg)` is therefore `sodium_mg`.
  - The unit the source prints becomes the suffix — `kcal`, `g`, `mg`, `ug`, `pct`.
    It is not decoration: 리놀레산 ships as both `(g)` and `(mg)`, and 비타민 A as
    both `(μg RAE)` and `(μg)`, so the suffix is what keeps the pair distinguishable.
  - One concept, one key across both directions. `MAKER_NM` is `maker_name` on the
    way out and on the way back; a column that is both a filter and a result must not
    answer to two names in the same contract.
  - The keys are only as good as their audit: the migration keeps `key`, `wire_path`
    and `description` on one line so a wrong pairing is visible where it is written,
    and `listWireNamedCallerKeys()` fails the gate when a `CALLER` filter key is
    nothing but its upper-case wire name lower-cased. That guard exists because the
    convention was stated here and enforced nowhere: a benchmarked run seeded
    `chng_dt`/`CHNG_DT`, `prdt_nm`/`PRDT_NM` and `brcd_no`/`BRCD_NO` and passed every
    hook and all 150 tests. Path parameters are exempt by construction — their
    `wire_path` is already the caller's word and lower-case (`range_start`).
- Never make a `required` row a field the provider omits for sparse records: public
  APIs return `null`/empty for unpopulated fields, and a `required` row on such a
  field turns a normal response into a 502. Exactly one required row per operation is
  the working shape — the field that makes the record the record.

## Response Formats (JSON, XML, HTML, CSV)

`integration_operation.response_format` is `JSON` (default), `XML`, `HTML` (a
screen) or `CSV` (a file), enforced by `ck_integration_operation_response_format`.
The first two resolve through the same `integration_field.wire_path` mapping:

- `JSON` — body parsed with `response.json()`.
- `XML` — body parsed with `xml.etree.ElementTree`, then converted to the nested
  dict shape pointers address: the root tag is dropped, leaf elements become
  their stripped text (empty element → `null`), and repeated sibling tags become
  lists. `<items><item>…</item><item>…</item></items>` is addressed as
  `/body/items/item/0/FIELD`.
- Malformed bodies map to `IntegrationError` (502) — "not valid JSON" or
  "not valid XML" — never a raw parser traceback.
- A provider offering both formats (e.g. MFDS `type=xml|json`) keeps the wire
  parameter as a `LITERAL` request field whose value matches `response_format`.

## Schema Naming and Ordering

`schemas/integration/*.py` follows the `backend-domain.md` suffix convention
exactly — every HTTP-facing class carries a `Request` or `Response` suffix:

- Request side: `IntegrationCreateRequest`, `IntegrationUpdateRequest`,
  `IntegrationExecuteRequest`, and the nested `*CreateRequest` classes
  (`IntegrationSecretCreateRequest`, `IntegrationFieldCreateRequest`,
  `IntegrationOperationCreateRequest`).
- Response side: `IntegrationReadResponse`, `IntegrationExecuteResponse`, and the
  nested `*ReadResponse` classes (`IntegrationSecretReadResponse`,
  `IntegrationFieldReadResponse`, `IntegrationOperationReadResponse`).
  `IntegrationSecretReadResponse` **omits** `value`.
- Suffix-free classes are limited to `IntegrationBase` and the `*Internal`
  classes (`IntegrationCreateInternal`, `IntegrationUpdateInternal`) — they are
  never HTTP bodies.
- Class ordering is consumption order: request-side classes first, then
  response-side, then update-side, then standalone request/response pairs, then
  `to_read()`/`to_read_list()` helpers last. Nested child classes precede the
  parent that references them.

Machine-checked by `check-backend-integration-configuration.ts`.

## Migration and Testing

- Each new configuration table has its own Alembic revision and reversible downgrade.
- A seed for an additional operation uses one revision per affected table:
  secret (when the provider needs a new credential), operation, then fields.
  Never create another provider row when the provider already exists.
- Replacing a seeded provider/operation (new endpoint, schema change) uses
  `_replace_` migration revisions — one per table — that DELETE the old rows
  (via `table().delete()` for UUID-safe cross-dialect binding) and re-INSERT.
  `_replace_` migrations supersede `_seed_` migrations for contract-test anchors.
  An operation replace runs **before** the field seed it owns: deleting the
  operation row cascades its fields away.
- **Correcting a provider row in place uses a `_correct_` revision, never a
  `_replace_`.** A provider replace deletes the row and the cascade takes every
  operation seeded before it, so a change that touches no operation — a wrong
  `display_name`, a `code` that names a different portal than its own `base_url`
  — is an UPDATE on the seeded id. The seed string in `PROVIDER_ID` keeps its
  historical spelling: it is the primary key thirty revisions derive ids from.
  `check-backend-migrations` rejects a delete inside a `_correct_` upgrade.
  Corrections are **cumulative, not superseding**: `_replay_newest_integration_seeds`
  takes the newest seed per (owner, table) *and* every later correction, in
  revision order. Replaying only the newest file would run the UPDATE without the
  INSERT it corrects and leave the row absent — and skipping corrections entirely
  left the replayed database answering `mfds-food-nutrition` (measured) while every
  real database answered `data-go-kr`.
- Register all four models in `alembic/env.py` and test conftest metadata.
- Integration unit tests (`tests/core/test_integration.py`) cover
  `IntegrationClient` mechanics: request rendering, request-schema failure,
  response mapping, passthrough roots, retry, timeout, transport failure, rate
  limiting, database resolution, serializers, pointers, and shared-client lifecycle.
- **Contract fixtures, not hand-written contract tests.** One parametrized test
  (`test_execute_renders_the_seeded_contract`) builds the client from the
  **replayed seeds** and drives it against one recorded exchange per fixture in
  `tests/core/fixtures/integration/`. A new seeded operation adds
  `<operation-code>.json`; it never adds a test function. Enforced by
  `check-backend-integration-configuration.ts`, which also rejects a
  re-introduced `test_execute_renders_<operation>_contract`.
- A fixture carries **only what was measured**: `inputs` the caller sent,
  `response` the provider answered, and `expect` — the rendered `path`, any
  `query` pairs, `status_code`, `canonical_payload`, `metadata`. A refusal is a
  contract too: `expect.raises` with the message fragment, in a
  `<operation-code>.<variant>.json` file.
- **A fixture never restates the field list.** That was the whole defect of the
  hand-written form: the rows appeared in the seed and again in the test, so the
  copy could agree with itself while disagreeing with the database. Measured when
  the fixtures replaced them - one test still asserted a `page_no` LITERAL the
  seeds had made a required CALLER input, and three asserted 2 response keys
  where the seeds map 17, 18 and 19.
- The seed test replays the newest seed revision **per table that still exists in
  the models**, because each `_replace_` fully replaces its table's rows and seeds
  for dropped tables cannot run against the current schema. Discovery stays
  filesystem-driven; never hardcode revision numbers.
- Rules that are not per-operation configuration stay unit tests: the envelope
  verdict rules (`PRESENT`, `EXACT`, a missing value) are parametrized directly
  against `_envelope_holds`, because they describe the checker, not one provider.

## Never Do These

- Persist credentials, API keys, request bodies, or response bodies in logs or
  audit trails. (Credentials live in `integration_secret.value`, never echoed by
  any API response.)
- Keep integration secrets in environment variables — the only secret store is
  `integration_secret`.
- Store a secret value on a field row, or reference a secret from a non-`SECRET`
  field.
- Allow direct `httpx2` usage outside `app/core/integration.py`.
- Forward arbitrary external response headers to callers.
- Add `config_revision`, cache invalidation, or dynamic expression languages without
  an explicit operational requirement.
- Merge multiple configuration tables into one migration revision.
- Write a per-operation contract test by hand. The field list belongs to the seed;
  a test that restates it tests its own copy.
- Leave a fixture's `expect.path` unmeasured (a placeholder, a guess): the
  rendered path is the half of the contract the provider judges.
