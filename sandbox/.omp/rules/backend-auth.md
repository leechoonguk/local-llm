---
description: Backend auth — JWT login, current_user injection, domain exception patterns
globs:
      - backend/app/routers/auth.py
      - backend/app/dependencies/auth.py
      - backend/app/core/security.py
      - backend/app/core/exceptions.py
      - backend/app/routers/*.py
      - backend/app/services/*.py
alwaysApply: false
---

# Backend Auth

## Authentication

JWT-based auth (FastAPI OAuth2 password flow):

- `POST /auth/login` — `OAuth2FormDep` (username/password) →
  verifies against `user.hashed_password` (pwdlib argon2) → returns
  `{access_token, token_type: "bearer"}`
- `GET /auth/me` — returns the current user from the Bearer token
- `dependencies/auth.py` — `oauth2_scheme` (`OAuth2PasswordBearer`),
  `get_current_user` (decodes JWT `sub` = user id, loads the user,
  `expunge` + `rollback` to release the read transaction), `CurrentUserDep`
- `core/security.py` — `hash_password`/`verify_password` (pwdlib),
  `create_access_token`/`decode_access_token` (PyJWT, HS256)
- Settings: `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES` (default 30),
  `ALGORITHM` (default HS256) in `backend/.env` + `settings.py`
- Protected routers inject `current_user: CurrentUserDep` and use
  `current_user.username` for `created_by`/`updated_by` — never `"system"`

## Endpoint Auth Policy

**All endpoints require authentication** — only `POST /auth/login`,
`POST /user/` (signup), and `GET /health` (readiness) are public.
Machine-checked by `router/auth-all.yml`.

| Endpoint | Auth | Rule |
|---|---|---|
| `POST /auth/login` | public | `auth-all.yml` exception |
| `POST /user/` (signup) | public | `auth-all.yml` exception |
| `GET /health` (readiness) | public | `auth-all.yml` exception |
| all other endpoints | `current_user: CurrentUserDep` | `auth-all.yml` |
| `PUT`/`DELETE` | `current_user: CurrentUserDep` | `write-auth.yml` |
| `current_user` outside routers | forbidden | `conventions/current-user-router-only.yml`

## Exceptions

Service → API error pattern (`core/exceptions.py`):

| Exception | Raised where | Response |
|---|---|---|
| `NotFoundError` | services — resource not found (get/update/delete) | `404` |
| `ConflictError` | services — unique constraint / duplicate (e.g. username/email) | `409` |
| `AuthenticationError` | services — invalid credentials | `401` |

- Services raise **domain exceptions** (`NotFoundError`/`ConflictError`) — never `HTTPException`
  (checked by `service/http-exception.yml`, services/ scope)
- Services must only raise exceptions defined in `core/exceptions.py` — a
  standard exception (`ValueError`, `RuntimeError`) has no handler and would
  surface as HTTP 500 (checked by `check-backend-domain.ts` service-exception scan)
- `setup_exception_handler` in `core/exceptions.py` registers one
  `@app.exception_handler` per domain exception — a new exception without a
  handler surfaces as 500 (checked by `check-backend-domain.ts` exception sync)
- Routers may raise `HTTPException` directly (e.g. 401 login failure in auth)

**Adding a new domain exception** (all 3 steps machine-checked):

1. `class XxxError(Exception)` in `core/exceptions.py`
2. `@app.exception_handler(XxxError)` in `setup_exception_handler`
3. `raise XxxError(...)` in services


## Actor Attribution

`created_by`/`updated_by` name **who** made the change, so they come from the
authenticated caller: `current_user.username`.

`"system"` is correct in exactly one place - a **public** endpoint, where there
is no caller to name. `POST /user/` (signup) is the only such write today.
`ast-grep/rules/auth/system-actor.yml` therefore scopes the ban structurally: a
literal `"system"` is a violation only inside a function that has
`current_user` in scope. A blanket ban would have made the correct signup code
a violation, which is why the earlier wording never became a check.

## Token Claims and Password Cost

- **`iat` on mint, `["exp", "sub"]` required on decode.** A token with no `exp`
  never expires and one with no `sub` authenticates nobody; both are rejected at
  the decode, not downstream. `iat` dates the token, so a leaked one can be told
  apart from a fresh one.
- **Hashing never runs in the event loop.** argon2 costs ~25 ms of CPU per hash
  and per verify (measured on this machine). Called straight from an async
  service that time is stolen from every other request in the process, so it goes
  to a worker thread: `await to_thread.run_sync(hash_password, password)`.
  Enforced structurally by `ast-grep/rules/offload/password-hash.yml` —
  passing the function as a reference is not a call, so the compliant form does
  not match.

## Never Do These

- `created_by="system"` / `updated_by="system"` — use `current_user.username`
- `HTTPException` in services — raise domain exceptions
- Standard exceptions (`ValueError`, `RuntimeError`) in services — no handler → 500
- `current_user: CurrentUserDep` outside routers (services/repositories/core)
- Inline `Depends()`/`Query()` in routers — use Annotated aliases
