---
description: Backend testing — API/service/batch test standards, 100% coverage gate
globs:
      - backend/tests/**/*.py
      - backend/pyproject.toml
      - backend/app/batch/*.py
alwaysApply: false
---

# Backend Testing

## Purpose

Every backend behavior — API endpoints, service layer, batch jobs — must be
covered by tests, and the suite must hold **100% line coverage** of `app/`.
The coverage gate is enforced by `make test` (`--cov-fail-under=100`).

## Coverage Gate

- `backend/pyproject.toml` sets `addopts = "--cov=app --cov-report=term-missing --cov-fail-under=100"`
- `make test` fails when total coverage < 100%
- Excluded from coverage (no testable logic):
  - `app/main.py` — FastAPI entry point
  - `app/core/database.py` — engine construction
  - `if __name__ == "__main__":` blocks — `# pragma: no cover`
- A new module must reach 100% before `make verify` passes

## Test Folder Structure

Tests are organized by layer, mirroring what they exercise. Repository and
service tests are split **per source module**:

```
backend/tests/
├── conftest.py              # shared fixtures (client, auth_headers, engine, factory)
├── api/                     # HTTP API tests (routers)
│   ├── test_<domain>.py     # one per CRUD domain — 10 standard cases
│   └── test_auth.py         # auth standard (login, /auth/me, 401 paths)
├── batch/                   # batch job tests
│   └── test_<module>.py     # mirrors app/batch/<module>.py (e.g. test_batches.py)
├── repositories/            # repository unit tests — one file per source module
│   └── test_batch.py  test_user.py
├── services/                # service unit tests — one file per source module
│   ├── test_batch.py  test_user.py
│   └── integration/         # multi-file domain — mirrors app/services/integration/
└── core/                    # core unit tests
    ├── test_exceptions.py   # domain exceptions + handler registration
    ├── test_security.py     # password hashing + JWT
    └── test_settings.py     # Settings model defaults/validation
```

| Folder | Covers | File naming |
|---|---|---|
| `tests/api/` | HTTP endpoints via TestClient | `test_<domain>.py`, `test_auth.py` |
| `tests/batch/` | `app/batch/*` jobs against in-memory engine | `test_<module>.py` (mirrors source module) |
| `tests/repositories/` | repositories directly | `test_<module>.py` (mirrors `app/repositories/`) |
| `tests/services/` | services directly (success + domain exceptions) | `test_<module>.py` (mirrors `app/services/`) |
| `tests/core/` | core modules (exceptions/security/settings) | `test_<module>.py` (mirrors `app/core/`) |

Each subdirectory has an `__init__.py` — pytest needs unique module basenames
across directories (`test_batch.py` exists in api/, repositories/, services/).

## API Test Standard (`tests/api/test_<domain>.py`)

Every CRUD domain test file follows the same pattern:

1. **Create** — `POST /<domain>/` → 201, body has `id`
2. **List** — `GET /<domain>/` → 200, contains created names
3. **Get** — `GET /<domain>/{id}` → 200
4. **Get 404** — `GET /<domain>/00000000-0000-0000-0000-000000000000` → 404
5. **Update** — `PATCH /<domain>/{id}` → 200, field changed (verb follows the update schema — rule://backend-api-http)
6. **Update 404** — `PATCH /<domain>/00000000-...` → 404
7. **Delete** — `DELETE /<domain>/{id}` → 200 `{"ok": true}`, then GET → 404
8. **Delete 404** — `DELETE /<domain>/00000000-...` → 404
9. **Create 422** — `POST /<domain>/` with a missing required field → 422
10. **Unauthorized** — `GET /<domain>/` without a token → 401

Fixtures: `client` (in-memory SQLite) + `auth_headers` (Bearer token).

**The ten cases are the one-table standard.** A domain that owns several model
files is not a one-resource CRUD API, so the ten test-name patterns and the
per-table repository test file do not describe it — its behavioral contract
does. Which standard applies is decided structurally, by how many model files
the domain owns (`aggregateDomains()` in `lib/backend-domain-structure.ts`),
never by a domain name in a hook.

`integration` is the current multi-file domain: its API, service, and core
tests are governed by `backend-integration-configuration.md` and validated by
`check-backend-integration-configuration.ts`.

## Auth Test Standard (`tests/api/test_auth.py`)

- login success → 200 + `access_token`
- login wrong password → 401
- login unknown user → 401
- `/auth/me` with valid token → 200
- `/auth/me` without token → 401
- `/auth/me` with invalid JWT → 401
- `/auth/me` with valid JWT but missing user → 401
- `/auth/me` with non-UUID subject → 401 (ValueError path)

## Batch Job Test Standard (`tests/batch/test_<module>.py`)

- One file per source module: `app/batch/batches.py` → `tests/batch/test_batches.py`
- Swap `app.batch.<name>.engine` for an in-memory engine (fixture)
- Seed rows, backdate `created_at` via `__table__.update()`
- Assert the job's count/status return
- Cover the `except NotFoundError` skip path (monkeypatch `delete_batch`)

## Repository Test Standard (`tests/repositories/test_<module>.py`)

One file per source module in `app/repositories/` — CRUD + `find_stale` +
domain-specific lookups (`get_by_username`/`get_by_email` for user). Uses the
shared `engine`/`factory` fixtures from conftest.

## Service Test Standard (`tests/services/test_<module>.py`)

One file per source module in `app/services/`. Every public method of the
service class must be called directly — HTTP tests alone cannot cover
service-layer contracts (NotFoundError raising, transaction boundaries,
ConflictError on duplicates, AuthenticationError on bad credentials).

| Service | Methods to cover |
|---|---|
| `BatchService` | get, list, find_stale, create, update, delete |
| `UserService` | get, get_by_username, authenticate, list, create, update, delete |

Each method is tested for:
- **success path** — returns the expected entity/list
- **error path** — raises the domain exception (`NotFoundError`, `ConflictError`,
  `AuthenticationError`) when the precondition fails

Each request step runs in its **own session** (mirroring the router's
`get_session()` lifecycle) — a read autobegins a transaction, and the next
write's `session.begin()` would collide on the same session.

Machine-checked by `check-backend-tests.ts` (check 8 — every service module
has a test file and every method is referenced there).

## Core Test Standard (`tests/core/`)

Every module in `app/core/` must have a matching `tests/core/test_<module>.py`
— core logic (exception handlers, JWT, settings) is infrastructure that HTTP
tests exercise only indirectly:

| Module | Test file | Covers |
|---|---|---|
| `exceptions.py` | `test_exceptions.py` | exception attributes, `setup_exception_handler` 404/409/401 |
| `security.py` | `test_security.py` | password hash roundtrip/salt, JWT encode/decode/expiry/tamper |
| `settings.py` | `test_settings.py` | defaults, overrides, required fields, extra ignored |

Machine-checked by `check-backend-tests.ts` (check 9 — every core module has
a test file).

## Conftest Contract

`tests/conftest.py`:

- `settings.env = "test"` — disables the scheduler
- `client` fixture swaps `app.dependencies.core.async_session_factory` to an
  in-memory SQLite engine — the **real** `get_session()` dependency runs
  (request lifecycle exercised, no dependency override)
- `auth_headers` fixture creates a user + logs in, returns Bearer headers
- Every model imported (`from app.models.<name> import <Name>`) so
  `Base.metadata.create_all()` builds all tables
- `isolate_settings_environment` — an **autouse** fixture that deletes every
  `Settings` field name from `os.environ` (upper and lower case), derived from
  `Settings.model_fields`

**Why hermetic environment matters.** `Settings(_env_file=None, …)` bypasses the
`.env` file but not the process environment: pydantic-settings reads `os.environ`
first. A shell or CI job that exported the root `.env` (`REDIS_URL`,
`ITEMS_PER_USER`, …) changed what the settings tests observed — the same commit
was green in one terminal and red in another, which was measured, not imagined.
Deriving the names from the model means a new field cannot reintroduce the leak.

## Never Do These

- Ship a new module without 100% coverage — `make test` fails
- Write a docstring that only rearranges the test's own name
- Leave a test module or test function without a docstring
- Use `# pragma: no cover` on logic — only on `__main__` entry points
- Test with a dependency override instead of the real `get_session()`
- Skip the 404/401 error paths — they are part of the contract
- Leave `find_stale`/`get_by_username` untested because "HTTP doesn't call them"
- Assert on settings defaults without the autouse env-isolation fixture — the
  process environment decides the result, not the code
- Add a router endpoint without a test hitting that path — `check-backend-tests`
  flags any `@router.<method>` without a matching path reference in the api test
- Add a batch job function without a test in `tests/batch/test_<module>.py` — the
  scheduler is disabled under `settings.env == "test"`, so an untested job
  fails silently in production
- Add a service method without a test in its `tests/services/test_<module>.py` —
  `check-backend-tests` flags any public service method not referenced there
- Add a repository/service module without `tests/<layer>/test_<module>.py` —
  the per-module split is part of the standard
- Add a core module without `tests/core/test_<module>.py` — core logic is
  infrastructure that HTTP tests exercise only indirectly
- Put an API test in `tests/repositories/` or a unit test in `tests/api/` — the
  folder structure is part of the standard

## Docstrings

A test names a contract; the docstring says **why that contract exists** - what
breaks without it, or which failure mode it closes. The name already says what
is exercised, so a docstring that rearranges the name is noise.

- **Module docstring, always** - one line naming the surface under test.
- **Function docstring, always** - the reason the case is a contract. When the
  test is one of several around the same behaviour, say what *this* one adds
  (the wrong direction, the second cutoff, the duplicate delete).
- **Never restate the name** - `"""Test create user."""` on `test_create_user`
  adds nothing. `check-backend-tests` fails when a summary contains no word
  beyond the function name and filler.
- **A test-local closure is private** - a handler defined inside a test needs no
  docstring of its own; the test's docstring covers it.

Presence is owned by the toolchain (`ruff`'s `pydocstyle` `D` rules in
`pyproject.toml`, selected for `tests/**`), substance by
`check-backend-tests.ts`. Neither can be satisfied by the other.

## Missing-Test Detection (check-backend-tests)

The hook detects missing tests structurally, beyond the coverage gate:

| Check | Detects |
|---|---|
| Folder structure | `tests/api/`, `tests/batch/`, `tests/repositories/`, `tests/services/`, `tests/core/` missing |
| Model → api test file | a domain with no `tests/api/test_<name>.py` |
| 10 standard API cases | an api test file missing create/list/get/update/delete (+404, +422, +401) |
| Status assertions | an api test file with no `status_code == 201/401/404/422` assertion — the standard cases are matched by name, so a case whose assertion is gutted (401 quietly becoming 200) would otherwise still count |
| Router endpoint → test path | an `@router.<method>` with no matching path in the api test |
| Batch job → test | an `async def` in `app/batch/*.py` not referenced by `tests/batch/test_<module>.py` |
| Repository module → test | a module in `app/repositories/*.py` with no `tests/repositories/test_<module>.py` |
| Service module → test | a module in `app/services/*.py` with no `tests/services/test_<module>.py` |
| Service method → test | a public method in `app/services/*.py` not referenced by its `tests/services/test_<module>.py` |
| Core module → test | a module in `app/core/*.py` with no `tests/core/test_<module>.py` |
| Auth standard | `tests/api/test_auth.py` missing any of the 8 auth cases |
| conftest contract | dependency override instead of real `get_session()` |
