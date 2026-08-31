---
description: Database-managed IntegrationClient configuration — provider, named secrets, operations, unified wire fields
globs:
      - backend/app/models/integration.py
      - backend/app/schemas/integration.py
      - backend/app/repositories/integration.py
      - backend/app/services/integration.py
      - backend/app/routers/integration.py
      - backend/app/core/integration.py
      - backend/app/core/settings.py
      - backend/alembic/versions/*_integration_*.py
      - backend/tests/api/test_integration.py
      - backend/tests/core/test_integration.py
      - backend/tests/services/test_integration.py
alwaysApply: false
---

# Backend Integration Configuration

## Overview

External HTTP configuration is stored in four tables and executed only through
`IntegrationClient`. Configuration is updated outside active calls; therefore
there is no configuration revision, configuration cache, or invalidation path.

## Data Model

- `integration_provider` owns `code`, HTTPS `base_url`, display name, and enablement.
- `integration_secret` owns one **named** credential per provider (`(provider_id, name)`
  unique). A field references it by FK, so a key is rotated in one place, survives a
  full replacement of an operation's fields, and is stored once no matter how many
  operations send it. Read responses expose the name, never the value.
- `integration_operation` owns method, relative path template, timeout/retry policy,
  idempotency, request JSON Schema, `response_format` (JSON|XML), and `response_root` —
  the whole response contract. **Mapping is the only response contract**: the RESPONSE
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
- **write time** — `IntegrationService._validate_response_root` refuses the same two
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

The four tables have two writers: alembic seeds, and `POST/PATCH /integration/`. A
migration reaches them through the DB `CHECK` alone — it never meets the Pydantic
literals or `IntegrationService`'s validation. So the same invariant is written three
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
| DB `CHECK` | the migration + `models/integration.py` |
| write-time validation | `services/integration.py` |
| request/response schema | `schemas/integration.py` |

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

## Response Formats (JSON and XML)

`integration_operation.response_format` is `JSON` (default) or `XML`, enforced by
`ck_integration_operation_response_format`. Both formats resolve through the same
`integration_field.wire_path` mapping:

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

`schemas/integration.py` follows the `backend-domain.md` suffix convention
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
