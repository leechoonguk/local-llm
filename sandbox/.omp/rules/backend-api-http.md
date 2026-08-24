---
description: Backend API test files — api/*.http structure, runnable CRUD sequencing, endpoint coverage, external API coverage
globs:
      - api/*.http
      - backend/app/routers/*.py
      - backend/app/models/*.py
      - backend/alembic/versions/*_integration_*.py
alwaysApply: false
---

# Backend API Test Files

An `api/<router>.http` file is the executable record of a router's contract. It
must be runnable **top to bottom, repeatedly, against a freshly migrated
database** without hand-editing an id. A file that needs a pasted UUID is not a
test — it is a note.

Everything below is machine-checked by `check-backend-api-http.ts`.

## Location Standard

Every `.http` file lives in the **repository-root `api/` directory** —
`backend/api/` is not a recognized location:

- a file's **router is its first dot-segment**: `integration.search-food-nutrition.http`
  is anchored to `routers/integration.py`, so a router owns one primary file and
  any number of companions
- an `api/*.http` whose first dot-segment names no router is an orphan
- a `backend/api/*.http` file is outside the checked tree and must be moved

## File Categories

The category is derived from the router, never hardcoded:

| Category | Detected by | Extra requirements |
|---|---|---|
| **CRUD** | router declares all five of `POST /`, `GET /`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}` | the full sequence below |
| **Special** | any other router (`auth`, `health`) | structure + coverage only |
| **Companion** | `<router>.<slug>.http` — one external operation per file | structure only; no CRUD sequence |

A CRUD router with extra endpoints (integration secrets, operation execute) is
still a CRUD file: the sequence comes first, the special blocks follow.

**External integrations are the exception to one-file-per-router.** Each seeded
operation owns `integration.<operation-code>.http` — a provider grows operations,
and one file would become a pile where no reader can tell which blocks belong to
which external API. The file name *is* the mapping, so no registry exists to
drift. Endpoint coverage reads the union of a router's files, so moving a block
into a companion never uncovers an endpoint.

### The chain a new integration must complete

| Step | Enforced by | What fails without it |
|---|---|---|
| Migration seeds `integration_operation` | discovery in `lib/backend-migration-policy.ts` — by **target table**, never by filename | a filename rule once dropped every `_seed_` file the moment a `_replace_` existed, hiding a live operation from every gate |
| Seed shape is readable | `listUnreadableOperationSeeds()` | raw SQL, a `bulk_insert` with no `"code"` literal, or rows handed over as a variable used to read as "no operation exists", so nothing was required. Measured twice: a regex that required the row list to end on its own line matched only multi-line literals, so the three newest operation seeds were invisible and discovery answered with a three-revision-old row |
| `api/integration.<code>.http` exists with an execute block | `check-backend-api-http` | the integration ships untested |
| Its declared status matches the seed state | same hook, joining operation ↔ `integration_field` seeds through their shared `uuid5` seed string | a half-seeded operation (row, no fields) claims a 200 it cannot serve — or a finished one keeps declaring 422 |
| That status is true against the stack | `make check-api-flow` | the declaration rots; the runner compares every block |
| A recorded exchange anchors the operation | `check-backend-integration-configuration` (fixture in `tests/core/fixtures/integration/<code>.json`) | request rendering and response normalization go unproven. The fixture never restates the seeded rows - the parametrized test builds the client from the replayed seeds, so a copy cannot agree with itself while disagreeing with the database |
| Discovery cannot drift between the two languages | `test_every_seeded_operation_owns_a_request_file` mirrors the TypeScript rule | two readers of the same migrations disagreeing is how the first gap opened |
| Every seeded CALLER input has a **200** block that sends it **alone** | `check-backend-api-http`, joining the operation's `integration_field` REQUEST rows | a seeded input nobody sends is an untested wire mapping — measured: six of `search-food-nutrition`'s seven CALLER fields had never been called once. A kitchen-sink block does not count, and the status is not what disqualifies it: seven filters together match no record, so once a page maps an empty result it answers 200 and would cover all seven while proving none. Only the one filter a block sends is proven by it; paging keys are exempt because every block states the window |
| A paging operation names its page | `check-backend-api-http` (seed side) + `IntegrationService._validate_response_root` (write side) | paging inputs with no `response_root` return a record for a call that asked for a window, and a root that pins an index (`/body/items/0`) returns the first row however large the page was — measured, and the reason the page-size input was unobservable |

Seed rows as `op.bulk_insert(<table var>, [ … "code": "…" … ])`. An operation
seeded without live `integration_field` rows cannot resolve its path template and
answers 422 — declare that in its request file until the seed is finished.

## Structure (every file)

1. **Title line** — `### <Name> API` on line 1.
2. **Prerequisites** — a `### 전제:` comment naming what must already exist.
3. **`@base`** — exactly `@base = {{$dotenv API_ORIGIN}}/api/v1`. The target is
   declared **once**, in `api/.env` (committed reference: `api/.env.example`), and
   never written into a request file: REST Client resolves `$dotenv` from the
   `.env` beside the `.http` file, and `check-api-flow` reads the same pair, so
   the editor and the runner cannot drift onto different servers. The declared
   value is an **origin** (`scheme://host:18000`, no path) because `/health` sits
   above the version prefix; `/api/v1` therefore stays visible in the files.
   A literal host was the previous rule and it rotted: five files pointed at a
   public IP while the check still demanded localhost.

   **`{{$dotenv …}}` never appears in a request line** — the space inside the
   template ends the target and the whole block is dropped (measured: 46 blocks
   became 45). A request above `/api/v1` takes a header variable instead:
   `@origin = {{$dotenv API_ORIGIN}}` then `GET {{origin}}/health`.

   **What may live in `api/.env`:** a value that varies per target *and* does not
   exist in the repository's deterministic state. The seeded actor is the
   counter-example — a migration creates it unconditionally, so a variable could
   only disagree with the database. Enforced both ways: every `{{$dotenv NAME}}`
   must be declared in `api/.env.example`, and every declared key must be used by
   a request file.
4. **Login block** — `# @name login` + `POST {{base}}/auth/login`, placed
   **before** the first request that carries a token. Required only when the file
   has at least one authenticated request: a purely public file (health
   readiness) does not need one.
5. **Numbered sections** — every request block opens with `### N. <title>`,
   numbered from `1` and increasing by exactly one. Gaps and repeats hide a
   dropped block during review.
6. **Expected status in the title** — the title declares what the block must
   return **after a dash**: `### 4. 단건 조회 — 200 (version=1)`. Only the code
   after the dash is the expectation, so prose may mention other codes
   (`— 201 (이미 존재하면 409, 그대로 진행)` declares 201). A block whose expected
   result is unwritten cannot be verified by the next reader.
7. **Bearer on every non-public request** —
   `Authorization: Bearer {{login.response.body.access_token}}`. Public
   exceptions: `POST /auth/login`, `POST /user/`, `GET /health`. A block whose
   title declares `401` omits the header on purpose — that is the case proving
   the endpoint rejects a missing token.
8. **Endpoint coverage** — every `@router.<method>` has a request block. Path
   parameters are matched one segment at a time, so `{{batchId}}` satisfies
   `{batch_id}`.
9. **No literal id in a request line** — ids come from variables. A hardcoded
   UUID in a URL is the defect this standard exists to remove: it makes `GET`,
   `PUT`, and `DELETE` return 404 on every run. Fixed ids that are genuinely
   seeded (a seed migration's provider) are declared once as a variable at the
   top of the file and referenced as `{{name}}`.

## Comments and Alignment

`###` is a **delimiter**, not a comment marker: REST Client starts a new section
at every `###` line. A narrative line written with three hashes silently splits
a block — the same class of defect as a `@var` inside a body, which answered 422.

```http
### User API — 계정 CRUD (username/email은 unique)          ← line 1: title
### 전제: backend 서버 실행 중 (cd backend && make dev) + …   ← prerequisites
### 순차 실행: 1번이 로그인하고, 2번이 만든 계정을 7번이 지운다.  ← flow
###           행위자 계정의 생성·삭제는 api/auth.http가 담당한다.  ← continuation, 11 spaces
@base = {{$dotenv API_ORIGIN}}/api/v1
# 체이닝 변수는 요청 블록 밖에 둔다 — 바디 뒤면 REST Client가 JSON에 붙인다   ← why
@userId = {{createUser.response.body.id}}
```

| Rule | Why |
|---|---|
| `###` only for: line 1 title, `### 전제:`, `### 순차 실행:` + continuations, `### N. …` | any other `###` starts a phantom section |
| every other comment uses `#` | it is a comment, not a boundary |
| header prose continuations indent **11 spaces** after `###` | aligns under `순차 실행: ` |
| every numbered section carries `— <status>` **and** a `(why)` parenthetical | the title says what is expected; the parenthetical says why |
| every variable except `@base` has a `#` line above it | a variable without a stated reason is a magic value |
| `@name = value` — one space each side | scanning a header should not need parsing |
| variables live in the header, before the first numbered section | REST Client sends anything after a body as part of it |
| 2-space body indentation, no tabs, no trailing whitespace, one final newline | diff noise is review noise |

Machine-checked by `check-backend-api-http` (`checkCommentLayout`).

## Variable Placement

**A `@var = ...` declaration never sits inside a request block.** REST Client
ends a request body at the next `###` delimiter and nothing else, so a
declaration written after the body is sent *as part of the body*:

```http
POST {{base}}/user/
Content-Type: application/json

{ "username": "user-{{$guid}}" }

@userId = {{createUser.response.body.id}}     ← appended to the JSON
```

The request answers `422 json_invalid` with `"Extra data"` at the offset of the
`@` — measured, byte 167 of that body. Declare chained variables **before the
first request**, in the header section next to `@base`; REST Client resolves them
lazily, at the moment they are used.

This was invisible to `check-api-flow` for a while because the runner treated
`@var` as a body boundary — more forgiving than the client it emulates. Both
halves are now strict: the parser ends bodies only at `###`, and
`check-backend-api-http` rejects a declaration inside a block.

## State Neutrality (every file)

Running **every** `api/*.http` file must leave the database exactly as
`make db-init` left it. A file that leaks a row makes the next run start from a
different state, and the suite stops being a regression test.

- **Balanced create/delete** — every block declaring `— 201` has a later block
  declaring `— 200` that deletes from the same collection. A child created inside
  its parent's payload needs no delete of its own: the parent's delete removes it
  by cascade.
- **One seeded actor, created by a migration** — the domain files (`user`,
  `batch`, `integration`) send the seeded credentials **verbatim**
  (`username=api-actor&password=api-actor-secret`) and name `make db-init` in
  their `### 전제:` line. They create **no account**. The row comes from
  `57_seed_api_actor_user.py`, which seeds **unconditionally** — a migration is a
  deterministic step, so no `ENV` or flag decides what rows exist.

  The credentials are not behind a `{{actorUsername}}` variable on purpose: when
  a client does not resolve it, the body is sent literally and login answers 401
  — measured, and indistinguishable from "the file is broken".
- **`auth.http` owns the account lifecycle** — create (`# @name createActor` →
  `POST /user/` — 201) → login chained from that response → the failure cases →
  `DELETE /user/{{actorId}}` — 200 as the **last** block. That lifecycle *is* the
  auth contract, so it is tested there and nowhere else.

  A per-file actor was tried and removed: `{{$timestamp}}` has one-second
  resolution, so re-running a file inside the same second answered **409 on
  block 1** (measured), an interrupted run leaked an account, and three files
  carried two blocks of setup unrelated to their domain.
- **The seeded actor is baseline, never test data** — it is a seeded row, so no
  file creates or deletes it and `check-api-flow` only verifies it can log in,
  failing with "apply the seed migration first" when it cannot. The seed skips
  `ENV=production`: a known password is a backdoor, and no `.http` suite runs
  there.
- **Seeded rows are never deleted** — a seed migration's fixed id is referenced
  through a variable and only ever read. The CRUD sequence operates on a
  throwaway resource the file creates and removes itself.
- **Dynamic values** — a created name that carries a uniqueness constraint uses
  `{{$guid}}`, not `{{$timestamp}}`. The timestamp has **one-second resolution**,
  so two runs inside the same second collide with 409 — measured: 201 then 409 on
  the same block. `{{$timestamp}}` stays acceptable for a field with no unique
  index (a batch name).

## Runtime Proof (`make check-api-flow`)

Declaring a state-neutral flow is not proving one. `make check-api-flow` runs
`.omp/hooks/lib/backend-api-flow.ts`, which executes **every** `api/*.http` file
the way REST Client would and proves the standard at runtime:

- **Chaining** — `{{name.response.body.*}}`, `@vars`, `{{$timestamp}}`,
  `{{$guid}}`, `{{$randomInt}}` are resolved per request, so a file that needs a
  hand-pasted id fails with `unresolved template`.
- **Declared status** — each block's response status must equal the status its
  section title declares after the dash. A drifted contract fails here.
- **State neutrality** — row counts (`public` tables, minus `alembic_version`)
  are snapshotted before and after **each** file and across the suite. A leaked
  or deleted row is reported per table (`user 0 → 1`).

The runner is CLI-only, never a post hook: it writes to the database and calls
external APIs, so it must be asked for. It needs the stack up (`make up`, or
`cd backend && make dev`) and postgres reachable (`make infra-up`); it is not
part of `make verify`, which stays hermetic.

`check-backend-api-http` verifies the proof still exists — the runner file and
the `check-api-flow` target that invokes it.

## Runnable CRUD Sequence (CRUD files)

The sequence is ordered so that each step's precondition is produced by an
earlier step, and the resource it creates is removed again — leaving the
database as it was, so the next run behaves identically.

```text
create → list → get → update → [conflict] → delete → [not-found] → [validation] → [unauthorized]
```

- **Chaining** — the create block is named (`# @name create<Domain>`) and the
  file declares `@<domain>Id = {{create<Domain>.response.body.id}}` immediately
  after it. `get`, `update`, and `delete` address `{{<domain>Id}}`.
- **The named block is the sequence's create.** A file may hold other POSTs to
  the collection — a 409 duplicate, a 422 case — and the ordering and
  dynamic-value rules apply to the named block only. No file except
  `api/auth.http` posts an account for its own login.
- **Conflict before delete** — a 409 case needs the resource alive, so it
  duplicates the just-created row and runs before the delete.
- **Not-found after delete** — a 404 case needs the resource gone. Reusing
  `{{<domain>Id}}` after the delete proves the delete worked; a dedicated
  `@missingId` variable is equally acceptable.
- **Re-runnable creates** — when the domain's model declares any uniqueness
  (`unique=True` or a `UniqueConstraint`), the create body must carry
  `{{$guid}}`. A static value 409s on the second run; `{{$timestamp}}` 409s on a
  second run inside the same second, which is what clicking "Run All" twice does.
- **Required failure coverage** — the file declares `404`, `422`, and `401`
  cases. A domain whose model declares uniqueness (`unique=True` or a
  `UniqueConstraint`) additionally declares a `409` case, placed before the
  delete: the duplicate is part of that domain's contract, and reproducing it
  needs the created row alive.

## External API Coverage (integration)

Every seeded external operation must be executable from `api/integration.http`.
Operation codes are discovered from the seed/replace migrations, so adding an
integration without adding its block is a failure:

- one **success-path (`— 200`)** `POST .../operations/<code>/execute` block per
  seeded operation code, carrying an `inputs` body. The 404 case names the same
  operation code, so only a block declaring 200 counts as coverage — otherwise a
  real integration could ship with its failure case alone
- the failure paths of execution: unknown operation (422) and unknown provider
  (404)
- the secret endpoints, including the referenced-secret delete conflict (409)

`{{seededProviderId}}` is the seeded provider UUID declared at the top of the
file, and `{{missingId}}` is the all-zero UUID used by the 404 paths. The seeded
provider is never deleted: the CRUD sequence operates on a throwaway provider it
creates and removes itself, so a run leaves the seeded configuration intact.

A seeded `path_template` is only callable when every `{placeholder}` in it has a
REQUEST `PATH` field whose `wire_path` fills it. A hole is not a documentation
slip: the client raises `Request path variables are unresolved` and the
operation answers 502 for every caller. Measured on a seed whose template ended
in `/{filters}` while the filters were `PATH_QUERY` rows that append their own
trailing segment - the request file would have been written against an endpoint
that could never answer.

## Never Do These

- Paste a literal UUID into a request line
- Leave `get`/`update`/`delete` pointing at an id the file never created
- Put a 404 case before the delete, or a 409 case after it
- Add an external integration without an execute block for its operation code
- Seed a `path_template` placeholder that no `PATH` field fills
- Number sections out of order, or omit the expected status from a title
- Write a host into `@base` instead of `{{$dotenv API_ORIGIN}}/api/v1`, or point
  `API_ORIGIN` at a port other than 8000, or give it a path
- Keep an `.http` file for a router that no longer exists
- Leave a created row behind, or delete a seeded row
- Create an actor account outside `api/auth.http` — one file owns that lifecycle
- Hide the seeded credentials behind a variable — an unresolved `{{…}}` is sent
  literally and answers 401, which reads as "the file is broken" (measured)
- Spell out a host in a request line, or reach the API through anything but
  `{{base}}` / `{{origin}}`
- Create or delete the seeded actor from an `.http` file — it is baseline state
- Omit `make db-init` from a file's `### 전제:` line
- Put any block after `auth.http`'s account delete
- Change an `.http` file without running `make check-api-flow` against the stack
- Delete the runner or its target, leaving state neutrality claimed but unproven
