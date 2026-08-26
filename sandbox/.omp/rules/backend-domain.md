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
| `models/` | `base.py` + one file per domain | `base.py` holds `Base` + `AuditMixin`; every other file is one domain model. |
| `schemas/` | one file per domain | Pydantic classes only — `Request`/`Response`/`Internal` suffixes, `to_read()`/`to_read_list()` helpers. |
| `repositories/` | one file per domain | Async CRUD — `get`/`list`/`find_stale`/`create`/`update`/`delete` + `__init__`. |
| `services/` | one file per domain | Thin adapter — `session.begin()` transactions, `NotFoundError`, domain-prefixed collaborators. |
| `routers/` | one file per domain | REST endpoints only — no business logic, no inline `Depends()`. |
| `batch/` | one file per job | Scheduled jobs — engine/session via services, never raw session usage. |

**Composition rules:**
- One file per domain across `models/` → `schemas/` → `repositories/` →
  `services/` → `routers/` — the model filename is the single source of truth
  for the domain name (all five layers use the same `<name>.py`).
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

**Specialized aggregate exception:** `models/integration.py` represents five
configuration tables, not a one-table CRUD resource. It follows the same
Model → Schema → Repository → Service → Router chain but is validated by
`backend-integration-configuration.md` and
`check-backend-integration-configuration.ts`, not the simple-domain checks.
- Router ↔ `api/*.http` sync and the .http content standard are documented in
  `backend-api-http.md`.

## Domain Creation

Each domain creates 5 layer files, wires 2 files, and lands 4 more artifacts.
The gate (`make verify`) checks every item below — missing any one fails:

**Creates (5 layers):**

- `models/<name>.py` — SQLAlchemy model with `AuditMixin` (`Base, AuditMixin`)
- `schemas/<name>.py` — 6 Pydantic classes: `XBase`, `XCreateRequest`, `XCreateInternal`, `XReadResponse`, `XUpdateRequest`, `XUpdateInternal`
- `repositories/<name>.py` — async CRUD repository with 7 methods: `get`, `list`, `find_stale`, `create`, `update`, `delete`, `__init__`
- `services/<name>.py` — thin service adapter with session-based `__init__`, `session.begin()` for transactions, raises `NotFoundError` (and `ConflictError` when the model declares uniqueness — see `services/user.py`)
- `routers/<name>.py` — 5 REST endpoints: POST `/`, GET `/`, GET `/{id}`, PUT `/{id}`, DELETE `/{id}` (list pagination uses the shared `OffsetQuery`/`LimitQuery` defaults — see rule://backend-router-params)

**Wires (2):**

- `dependencies/services.py` — `Annotated[T, Depends(factory)]` for all domain services (receive `SessionDep` directly)
- `main.py` — `app.include_router(name.router)` call

**Also lands (4) — checked by the gate, easy to forget:**

- `backend/alembic/versions/` — one revision via `make migrate-gen m="add <name> table"` (never hand-write the file), and `alembic/env.py` imports the new model
- `backend/tests/conftest.py` — imports the new model (`from app.models.<name> import <Name>`) so `Base.metadata.create_all()` builds its table
- `api/<name>.http` — request file per rule://backend-api-http (unique-constraint domains follow `api/user.http`: `{{$guid}}` + a `409` section)
- `backend/tests/{api,repositories,services}/test_<name>.py` — per rule://backend-testing

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
- Class names capitalized: `Item`, `Batch`, `Todo`, `BatchService`

## Model (`app/models/<name>.py`)

**Standard pattern** — `models/batch.py` is the reference:

```python
import uuid
from uuid import uuid4

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


class Batch(Base, AuditMixin):
    __tablename__ = "batch"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str | None] = mapped_column(default=None)
```

(The real file additionally carries the 62-char `# ==== … ====` section banners
required by rule://code-layout — copy the actual `models/batch.py`, not just
this excerpt.)

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
  `IntegrationRequestFieldReadResponse`, `IntegrationExecuteRequest`,
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
        #   self.user_service = UserService(session)

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
- Coverage standard lives in rule://backend-testing: 10 named API cases
  (+422/+401) plus separate `tests/repositories/` and `tests/services/` files.
  The gate matches **test function names** (e.g. a 404 case must contain
  `not_found` in its name)

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
- Every model except `base` (declarative base + mixins) and `integration` (a
  configuration aggregate with its own four-table contract) is validated. Never
  add a domain to that skip list to silence a failure: with the sample domains
  pruned, one skipped name can empty this hook.

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
