---
description: Backend domain conventions — 5-layer CRUD pattern, model/schema/repository/service/router, DI, testing
globs:
      - backend/app/services/*
      - backend/app/repositories/*
      - backend/app/routers/*
      - backend/app/dependencies/*
      - backend/app/models/*
      - backend/app/schemas/*
      - backend/app/core/database.py
      - backend/app/core/settings.py
      - backend/tests/conftest.py
      - backend/Makefile
alwaysApply: false
---

# Backend Domain

## Folder Structure

`backend/app/` is the only source tree. Every folder has a fixed composition
and a fixed per-file section layout (machine-checked by
`check-backend-domain.ts` / `check-backend-naming.ts`):

```
backend/app/
├── main.py              # FastAPI entry — Imports / Constants / Middleware /
│                        #   Lifespan / App Setup / Router Registration
├── core/                # infrastructure: settings, database, exceptions,
│                        #   security, logging, cache, integration transport
├── dependencies/        # DI wiring only — Annotated aliases + factories
├── models/              # SQLAlchemy ORM models (Base, AuditMixin, domain models)
├── schemas/             # Pydantic schemas (Request/Response/Internal)
├── repositories/        # async CRUD repositories (session-scoped)
├── services/            # thin service layer (business logic adapter)
├── routers/             # FastAPI APIRouter endpoints (RESTful CRUD)
└── batch/               # scheduled background jobs (APScheduler)
```

| Folder | Contains | Composition rule |
|---|---|---|
| `core/` | `settings.py`, `database.py`, `exceptions.py`, `security.py`, `logging.py`, `cache.py`, `integration.py` | Infrastructure only — no routers, no repositories. One module per concern. |
| `dependencies/` | `core.py`, `auth.py`, `query.py`, `services.py`, `integrations.py` | DI wiring only — `Annotated[T, Depends(factory)]` aliases and their factories. No business logic. |
| `models/` | `base.py` + one file per table | `base.py` holds `Base` + `AuditMixin`; a table per file, named after the table, in `models/<domain>/` once a domain owns several (`backend-model-files.md`). |
| `schemas/` | one file per domain, or `schemas/<domain>/` | Pydantic classes only — `Request`/`Response`/`Internal` suffixes, `to_read()`/`to_read_list()` helpers. |
| `repositories/` | one file per table | Async CRUD — `get`/`list`/`find_stale`/`create`/`update`/`delete` + `__init__`; `repositories/<domain>/` once a domain owns several (`backend-repository-files.md`). |
| `services/` | one file per domain, or `services/<domain>/` | Thin adapter — `session.begin()` transactions, `NotFoundError`, domain-prefixed collaborators. |
| `routers/` | one file per domain | REST endpoints only — no business logic, no inline `Depends()`. |
| `batch/` | one file per job | Scheduled jobs — engine/session via services, never raw session usage. |

**Composition rules:**
- **One file per domain per layer while the domain is one file; a folder named
  after the domain once it is several.** `models/` → `schemas/` →
  `repositories/` → `services/` → `routers/` all use `<name>.py`, and any of
  them may become `<name>/` — the domain name is the same either way, so a
  reader follows one name down the stack. Inside a folder the file drops the
  domain prefix (`models/integration/provider.py` maps `integration_provider`).
  The layer that decides a domain exists is `services/`.
- **Tests mirror the source path.** `services/integration/secret.py` is tested
  by `tests/services/integration/test_secret.py`, so a module's test lives at
  the module's own path (machine-checked by `check-backend-tests.ts`).
- `core/` and `dependencies/` are fixed sets — a new module there needs a
  matching `tests/core/test_<name>.py` (or `tests/` coverage) and a rule
  update; they are not per-domain.
- `batch/` mirrors `app/batch/<module>.py` → `tests/batch/test_<module>.py`.
- `.http` test files live in the repository-root `api/` directory, never
  `backend/api/` (backend-api-http.md).

## Structure Enforcement (Pre-Hook)

`strict-backend-app-structure.ts` blocks file creation at write/edit time,
before any check runs. Recognized locations only:

- `backend/app/<allowedDir>/...` — models, schemas, repositories, services,
  routers, dependencies, core, batch, tests
- `backend/app/main.py` and `backend/app/__init__.py` — the only files at the
  app root
- `backend/tests/`, `backend/alembic/`, `backend/scripts/` — standard backend dirs

Anything else is blocked: a new directory under `backend/app/` (e.g.
`adapters/`), a stray file at the app root (`backend/app/standalone.py`), or
a new directory under `backend/` outside the standard set (`backend/api/`,
`backend/workers/`).

**Never Do These**

- Add a file or directory outside the documented locations — the pre-hook
  blocks the write itself (post-hooks only flag files that already exist)

## 5-Layer Architecture

```
Model → Schema → Repository → Service → Router
```

Every domain follows this exact chain. Never skip a layer.

**Data chain is mandatory, router is optional:**

- `Model → Schema → Repository → Service` — required for every CRUD domain
  (machine-checked by `check-backend-domain.ts`)
- `Router` — optional. A domain may be internal-only (batch jobs) or exposed
  via a custom router (e.g. `auth.py` has no model/repo/service). When a router
  exists, its content (5 endpoints, UUID params, prefix) is validated.
- Schema-only modules (e.g. `schemas/auth.py` Token) are allowed — no model
  required for non-CRUD schemas.
- Router ↔ `api/*.http` sync and the .http content standard are documented in
  `backend-api-http.md`.

**A domain may own one table or many.** One table per model file is the table
rule (`backend-model-files.md`), and a domain owns the model files named after
it or prefixed `<domain>_`. Owning several is not an exception to the 5-layer
chain — the chain is identical either way; it only changes *which* checker
reads the domain's shape:

| Model files owned | Validated by |
|---|---|
| one | the simple-domain checks in `check-backend-domain.ts` |
| several | the per-file shape hooks (`check-backend-model-files.ts`, `check-backend-repository-files.ts`) plus the domain's own contract rule, when it has one |

`integration` is the current multi-file domain: five tables — the four
configuration tables governed by `backend-integration-configuration.md`, plus
the `integration_call` log. The split is discovered structurally
(`aggregateDomains()` in `lib/backend-domain-structure.ts`), so the next domain
to grow a second table needs no edit here and no name in a hook.

## Domain Creation

Each domain creates 5 files (one per layer) and wires 1 dependency file + main.py:

**Creates:**

- `models/<name>.py` — SQLAlchemy model with `AuditMixin` (`Base, AuditMixin`)
- `schemas/<name>.py` — 6 Pydantic classes: `XBase`, `XCreateRequest`, `XCreateInternal`, `XReadResponse`, `XUpdateRequest`, `XUpdateInternal`
- `repositories/<name>.py` — async CRUD repository with 7 methods: `get`, `list`, `find_stale`, `create`, `update`, `delete`, `__init__`
- `services/<name>.py` — thin service adapter with session-based `__init__`, `session.begin()` for transactions, raises `NotFoundError`
- `routers/<name>.py` — 5 REST endpoints: POST `/`, GET `/`, GET `/{id}`, the update endpoint on `/{id}` (verb follows the update schema — rule://backend-api-http), DELETE `/{id}`

**Wires:**

- `dependencies/services.py` — `Annotated[T, Depends(factory)]` for all domain services (receive `SessionDep` directly)
- `main.py` — `app.include_router(name.router)` call

A domain is not done at the five layers: the migration, the three test files
(`tests/{api,repositories,services}/`), `api/<name>.http`, and — because every
published route needs a browser caller (rule://frontend-contract) — the frontend
domain files are part of the same delivery.

### Build order (each step verifies its own layer before the next)

The order is not style: every late-loop failure measured on this baseline came
from deferring a step's verification until the end.

1. `models/<name>.py` → register in `alembic/env.py` **alongside** the existing
   imports → `make -C backend migrate-gen m="<real message>"` → **apply it
   immediately** (`make -C backend migrate`). An unapplied migration keeps the
   DB behind the files, and every later test run fails on that instead of on
   your code.
2. `schemas` → `repositories` → `services` → `routers` → wiring
   (`dependencies/services.py`, `main.py` — add alongside, never replace).
   After the router mounts: `make -C backend verify`.
3. Tests (three dirs) as each layer stands — not as a pile at the end.
4. `api/<name>.http` — **choose the exemplar by the domain's properties, not by
   habit**: a domain with a unique field follows the unique-domain exemplar
   (`{{$guid}}` + 409 section — rule://backend-api-http); a domain without one
   follows a plain sibling. Copying the wrong exemplar surfaces as a late gate
   failure on uniqueness.
5. Frontend domain files and wiring (both locales — the i18n check fails on a
   single-language key), then the full root `make verify`.

## Domain Naming

- `<name>` must be lowercase, alphanumeric (e.g. `todo`, `inventory`, `order`)
- Class names are auto-capitalized: `todo` → `Todo`, `inventory` → `Inventory`
- Table name = domain name: `todo` → `__tablename__ = "todo"`
- URL prefix = `/<name>`: `todo` → `/todo/`, `/todo/{todo_id}`
- File name = domain name (all lowercase): `item.py`, `batch.py`, `todo.py`
- File name format: `<name>.py` — lowercase alphanumeric (`^[a-z][a-z0-9]*$`),
  no hyphens/underscores/capitals. The model filename is the single source of
  truth: schemas/repositories/services/routers must use the same `<name>.py`
  (machine-checked by `check-backend-domain.ts`)
- Class names capitalized: `Batch`, `User`, `Todo`, `BatchService`

## Model (`app/models/<name>.py`)

**Standard pattern** — `models/user.py` is the reference:

```python
import uuid
from uuid import uuid4

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


class User(Base, AuditMixin):
    __tablename__ = "user"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
```

`models/batch.py` is no longer the plain-CRUD exemplar: its row *is* a
scheduled job (`code`, `cron`, `enabled` — rule://backend-batch), so a domain
copying it would inherit a scheduler contract it does not have.

Rules (all machine-checked by `check-backend-domain.ts`):

- `class X(Base, AuditMixin)` — inherits both `Base` and `AuditMixin`
- `id` is exactly:
  - `id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)`
  - checked by `model/id-standard.yml`
- Every other field follows the structure `$NAME: Mapped[$TYPE] = mapped_column(...)`
  — field **names are free**, only the Mapped/mapped_column structure is
  enforced (`model/field-mapped-pattern.yml`)
- `__tablename__ = "<name>"` (lowercase)
- Must import from `app.models.base`

## Schema (`app/schemas/<name>.py`)

6 Pydantic classes. **Naming convention**: requests and responses carry
`Request`/`Response` suffixes so the HTTP role is visible in the name:

| Class | Purpose | Required Fields |
|---|---|---|
| `<Name>Base` | Shared fields | `name: str`, `description: str \| None = None` |
| `<Name>CreateRequest` | **Request** — input for POST | inherits Base |
| `<Name>CreateInternal` | DB insert (internal, not HTTP) | inherits Base + `created_by: str` |
| `<Name>ReadResponse` | **Response** — output | inherits Base + `id`, audit fields, timestamps |
| `<Name>UpdateRequest` | **Request** — input for PUT | optional fields only |
| `<Name>UpdateInternal` | DB update (internal, not HTTP) | inherits Update + `updated_by: str` |

All schemas: `extra="forbid"`.
Read schemas: `from_attributes=True`.
Helper functions: `to_read()` and `to_read_list()` using `model_validate`.

**Convention rules:**
- `Request` suffix = HTTP request body (`XCreateRequest`, `XUpdateRequest`)
- `Response` suffix = HTTP response (`XReadResponse`, `TokenResponse`)
- `Internal` suffix = DB layer only, never exposed via HTTP (`XCreateInternal`, `XUpdateInternal`)
- **Every HTTP-facing schema class carries exactly one of the `Request`/`Response`
  suffixes** — a class without either suffix is a naming violation. This applies
  to nested aggregate schemas too: `IntegrationOperationCreateRequest`,
  `IntegrationFieldReadResponse`, `IntegrationExecuteRequest`,
  `IntegrationExecuteResponse`. `Base`/`Internal` classes are the only
  suffix-free exceptions (they are never HTTP bodies).
- **Class ordering** — schemas are declared in the order they are consumed:
  request-side classes first (`*CreateRequest`, `*CreateInternal`), then
  response-side (`*ReadResponse`), then update-side (`*UpdateRequest`,
  `*UpdateInternal`), then standalone request/response pairs
  (`*ExecuteRequest`, `*ExecuteResponse`), then `to_read()`/`to_read_list()`
  helpers last. Nested child classes precede the parent that references them.

## Repository (`app/repositories/<name>.py`)

7 methods, all `async`:

| Method | Signature | Returns |
|---|---|---|
| `get` | `get(<name>_id: UUID)` | `<Name> \| None` |
| `list` | `list(offset, limit)` | `list[<Name>]` |
| `find_stale` | `find_stale(older_than: datetime)` | `list[<Name>]` |
| `create` | `create(data: <Name>CreateInternal)` | `<Name>` |
| `update` | `update(<name>_id, data: <Name>UpdateInternal)` | `<Name> \| None` |
| `delete` | `delete(<name>_id: UUID)` | `bool` |

All use `AsyncSession`. All use `model_dump()` for serialization.
Import `UUID` from `uuid` in every repository.

## Service (`app/services/<name>.py`)

Thin adapter — no business logic beyond injecting `created_by` / `updated_by`, raising `NotFoundError` when a resource is not found.

```python
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

class NameService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.name_repository = NameRepository(session)
        # Multiple repositories/services use domain prefixes:
        #   self.user_repository = UserRepository(session)
        #   self.batch_service = BatchService(session)

    async def get_name(self, name_id: UUID) -> Name:
        o = await self.name_repository.get(name_id)
        if o is None:
            raise NotFoundError(name_id)
        return o

    async def create_name(
        self, data: NameCreateRequest, created_by: str
    ) -> Name:
        internal = NameCreateInternal(
            **data.model_dump(), created_by=created_by
        )
        async with self.session.begin():
            return await self.name_repository.create(internal)
```

**Injection naming** — services may inject multiple repositories/services, so
every internal collaborator is prefixed with its domain. Service variable
naming and repository encapsulation are documented in `backend-naming.md`
(machine-checked by `naming/var-name.yml`, `naming/repository-access.yml`,
`service/repository-param.yml`).

Rules:
- `__init__(self, session: AsyncSession)` — accepts `AsyncSession` directly
- Creates repositories internally with domain prefixes:
  `self.name_repository = NameRepository(session)`
- Uses `async with self.session.begin()` for transaction management (auto commit/rollback)
- `created_by` / `updated_by` injected as `str` from router
- `exclude_unset=True` on update only (not create)
- `NotFoundError` raised for get/update/delete when not found
- All methods are `async`

## Router (`app/routers/<name>.py`)

5 REST endpoints, matching CRUD:

| Endpoint | Method | Status | Returns |
|---|---|---|---|
| `POST /` | create | 201 | `NameReadResponse` |
| `GET /` | list | 200 | `list[NameReadResponse]` |
| `GET /{<name>_id}` | get | 200/404 | `NameReadResponse` |
| `PUT /{<name>_id}` | update | 200/404 | `NameReadResponse` |
| `DELETE /{<name>_id}` | delete | 200/404 | `{"ok": True}` |

Rules:
- `responses={404: {"description": "Not found"}}` on router
- `NotFoundError` caught by exception handler (set in `main.py`) — never raised inline
- `created_by` / `updated_by` injected from the authenticated user —
  routers use `current_user.username` via `CurrentUserDep` (JWT auth).
  See `backend-domain.md` "Authentication" and `dependencies/auth.py`.
- `to_read()` / `to_read_list()` for serialization

## DI Chain

```
core.SessionDep → <Name>ServiceDep → Router
```

```python
# dependencies/services.py
def get_batch_service(session: SessionDep) -> BatchService:
    return BatchService(session)
BatchServiceDep = Annotated[BatchService, Depends(get_batch_service)]
```

- `Annotated[T, Depends(factory)]` — never `Depends()` inline
- DI deps are `Annotated` aliases, not direct calls
- Services receive `SessionDep` directly (no intermediate repository dependency)

## Testing (`tests/`)

- `backend/tests/conftest.py`: in-memory SQLite, swaps `async_session_factory`
  so the real `get_session()` runs — no dependency override
- `settings.env = "test"` to disable scheduler
- One test file per domain: `tests/api/test_<name>.py`
- Tests cover: create, list, get, update, delete + not-found cases

## Validation (Post-Hook)

The `check-backend-domain.ts` post-hook validates the 5-layer structure after
tool execution. It delegates to per-domain modules; ORM ↔ DB sync and other
cross-cutting concerns are owned by their own hooks (see `omp-hooks.md`):

| Domain | Rule doc | lib module | Post hook |
|---|---|---|---|
| 5-layer structure | `backend-domain.md` | `lib/backend-domain-structure.ts` | `check-backend-domain.ts` |
| Auth + exceptions | `backend-auth.md` | `lib/backend-auth.ts` | `check-backend-auth.ts` |
| API test files | `backend-api-http.md` | `lib/backend-api-http.ts` | `check-backend-api-http.ts` |
| Naming | `backend-naming.md` | `lib/backend-naming.ts` | `check-backend-naming.ts` |
| ORM ↔ DB sync | `backend-migrations.md` | `lib/backend-orm-sync.ts` | `check-backend-migrations.ts` |

`check-backend-domain.ts` additionally enforces, per domain:

- **Every** Pydantic class that declares `model_config` carries `extra="forbid"` —
  checked per class, because one new class without it silently accepts unknown
  request fields while its siblings reject them.
- The Read response exposes `version: int`, so a client can observe the
  optimistic-lock revision it holds.
- The service **never** assigns `updated_at`. The repository sets it immediately
  before its `flush()`; a service assignment lands after the flush, costing a
  second `UPDATE` and a second `version` bump per request.
- Every model except `base` (declarative base + mixins) is validated. A domain
  that owns more than one model file (`integration`'s five-table configuration
  aggregate) is discovered structurally — by file ownership, not by a
  hardcoded name — so the next aggregate split needs no update to this hook.
  Never hardcode a domain name to skip it: that is the exact defect
  `aggregateDomains()`/`belongsToAggregateDomain()` in
  `lib/backend-domain-structure.ts` exist to remove.

**AST rules** (`.omp/ast-grep/rules/`, run by various post hooks per `omp-hooks.md` AST Rule Contract) add structural checks
string matching cannot express:

| Rule dir | Checks |
|---|---|
| `domain/` | service methods async, repository UUID params, transaction write-only |
| `router/` | write-auth, auth-all, inline-depends, response-model |
| `model/` | id-standard, field-mapped-pattern |
| `service/` | http-exception, repository-param |
| `naming/` | var-name, repository-access, inner-function-underscore |
| `conventions/` | current-user-router-only |
| `transaction/` | service-only |
| `batch/` | job-async, service-constructor, session-from-engine |
| `environment/` | os-environ-direct, hardcoded-connection, hardcoded-port |
| `ownership/` | check-missing |
| `audit/` | exposes-secret |
| `cache/` | no-ttl |
| `background/` | create-task |
| `upload/` | no-size-guard |
| `sse/` | streaming-response |

Warnings appear in the terminal — the user must fix violations before committing.

## Layer Enforcement

The layer boundary is visible at the import, so that is where it is checked:

- `ast-grep/rules/layering/repository-import.yml` - a router that imports
  `app.repositories.*` can read and write rows without the service that owns
  them: no ownership check, no conflict check, no audit columns.
- `ast-grep/rules/factory/from-session.yml` - a `from_session` factory builds its own
  dependency graph at the call site, so two callers get two different graphs and
  neither is the one DI wired.

## Review Judgement (not machine-checked)

"Business logic" has no syntactic form, so these stay with the reviewer:

- Logic in a router or repository that should live in the service.
- A service method that is a pass-through and hides no decision.
- Whether a domain deserves its own service at all.

## Relationship Loading

Every `relationship()` declares `lazy="raise_on_sql"`. Under asyncio there is no
safe lazy default: an attribute touched outside a loaded query raises
`MissingGreenlet` from inside greenlet plumbing, at whichever endpoint touches it
first. `raise_on_sql` moves the failure to the access itself with a sentence a
reader can act on, and turns "always eager-load" from a review habit into a
runtime guarantee — measured: dropping one `.options(selectinload(...))` fails the
test suite with `'Integration.secrets' is not available due to lazy='raise_on_sql'`.

Reads therefore eager-load what they return: `select(...).options(selectinload(...))`.

## Never Do These

- Skip a layer (e.g., router directly to repository)
- Business logic in router
- Business logic in repository
- `from_session` factory method (services accept session directly)
- Inline `Depends()` in router (use `Annotated` DI)
- `extra="allow"` on schemas
- Missing `from_attributes=True` on Read schemas
- Missing `extra="forbid"` on any schema
- `int` primary keys — ids are `UUID` (`Mapped[uuid.UUID]`, `default=uuid4`)
