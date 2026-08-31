---
description: Environment — .env conventions (root docker-compose + backend), settings.py, root↔backend sync
globs:
      - .env*
      - backend/.env*
      - backend/app/core/settings.py
      - backend/app/models/base.py
alwaysApply: false
---

# Environment

## .env File

All backend environment variables live in `backend/.env` (with `backend/.env.example` as a committed reference). The root `.env.example` is for **docker-compose** — it feeds `docker-compose.yml` (service ports, backend URLs, and `APP_NAME`/`ADMIN_EMAIL`/`ITEMS_PER_USER` passed to the backend container as environment). The backend app itself reads `backend/.env` via Pydantic settings.

A third pair sits outside the app's settings: **`api/.env`** (reference:
`api/.env.example`) declares `API_ORIGIN`, the one target every `api/*.http`
resolves `{{base}}` (and `{{origin}}`) from. It is client-side configuration, not
a Pydantic setting — REST Client reads `$dotenv` from the `.env` beside the
request file, which is why the pair lives in `api/` and not at the root.
`check-environment` does not look at it; `check-backend-api-http` owns it: the
key is present in the committed example, its value is an origin
(`scheme://host:28000`, no path), every `{{$dotenv …}}` a request file uses is
declared there, and every declared key is used. Values in **this** pair may
differ — the example points at localhost while a developer's `api/.env` points
at whatever serves them — because per-target is the whole purpose of the file.

### Source Precedence: the File Wins

`pydantic-settings` defaults to the process environment outranking the dotenv
file. That default cost this project twice — `alembic check` compared nothing and
reported dormant, and a server answered 500 on `/health` — both times because a
shell carried docker-compose's values and every local run silently pointed at
hosts that resolve only inside compose.

`Settings.settings_customise_sources` therefore returns
`(init, dotenv, env, secrets)`: **`backend/.env` outranks an exported variable**.
The fix lives in the schema (1), not in the callers, so it holds for every entry
point — `make` targets, a bare `uvicorn`, pytest in an editor, CI, or a
process manager. Earlier revisions stripped the 16 owned keys with `env -u` in
`backend/Makefile` and kept a hook to diff that list against `settings.py`; both
were the same contract written a fourth and fifth time, and both are gone.

The container is unaffected: `backend/Dockerfile` copies `pyproject.toml`,
`uv.lock`, `app`, `alembic`, `alembic.ini` and `scripts` — **no `.env`** — so the
dotenv source is empty there and docker-compose's environment remains the only
input. Defended by `backend/tests/core/test_settings.py`, not by a hook: it is a
behaviour of the code, so a test is the honest place for it.

**Consequence to know:** a per-process override (`ENV=… uvicorn …`) no longer
wins over `backend/.env` for a key the file declares. Change the file, or remove
the key from it.

### docker-compose: the Backend Maps the File

The backend service is configured by **mapping the root `.env` as a file**, not
by listing one key per line:

```yaml
# docker-compose.yml (correct — one mapping, no per-key list)
backend:
  env_file:
    - .env
```

A per-key `environment:` block is a second declaration of the settings schema,
and the copy is what goes stale. Measured on this repository: `SECRET_KEY` was
never added to that list, `settings.py` declares it with no default, and the
backend container therefore failed Pydantic validation on boot and restarted
forever — while `make verify` stayed green and every env-file check passed. The
image copies no `.env` (`backend/Dockerfile`), so compose is the container's only
input; a forgotten line is a setting that silently does not exist.

`settings.py` sets `extra="ignore"`, so root-only infra keys (`POSTGRES_*`,
`PHOENIX_*`, the host ports) are handed over harmlessly.

**Every other service keeps explicit values**, because a database must not
receive the app's signing key. Their entries must still be `${VAR}` references
resolved from the root `.env` — a literal in the compose file is configuration
in the wrong place. A container-local binding (`PHOENIX_HOST: "0.0.0.0"`) is the
documented exception: no deployment changes it.

Machine-checked by `check-environment.ts` (check 5): the backend declares
`env_file: [.env]` and **no** `environment:` block; every other service's values
are `${VAR}` references that root `.env` defines.

### Host Ports Are Configurable, Container Ports Are Not

Host-side ports come from the root `.env` with a default
(`"${POSTGRES_PORT:-25432}:25432"`), because a developer who already runs
PostgreSQL locally cannot start the stack when 25432 is taken. The container side
never moves: `DATABASE_URL`, `REDIS_URL` and the Phoenix SQL URL all name the
in-network port, so changing it would break every one of them.

```bash
# root .env / .env.example — host ports
POSTGRES_PORT = 25432
REDIS_PORT = 26379
PHOENIX_UI_PORT = 26006
PHOENIX_GRPC_PORT = 24317
BACKEND_PORT = 28000
FRONTEND_PORT = 25173
```

### ENV: container vs local (intentional mismatch)

`ENV` exists in **both** root `.env` and `backend/.env`, but with
**intentionally different values**:

- root `.env` — `ENV = production` — the **docker container** runs the
  production-grade stack (`make up`)
- `backend/.env` — `ENV = local` — **local development** (`cd backend && make
  dev`) uses debug settings and disables the scheduler

Unlike `APP_NAME`/`ADMIN_EMAIL`/`ITEMS_PER_USER` (values must match), `ENV`
is deliberately divergent — do not "sync" it.

### Env File Format (root .env style)

Every env file (root and backend) uses the root `.env` style:

- A `# ===...` header banner at the top (file purpose + how it is read)
- `# --- <Section> ---` markers grouping related variables (≥2 sections)
- A `# <description>` comment line above any variable that needs one
- Every assignment uses the aligned **`KEY = value`** form — a space on both
  sides of `=` (`KEY=value`, `KEY =value`, `KEY= value` are all rejected)
- Same keys, the same `# --- <Section> ---` markers, and the same
  per-variable preceding comment across `.env` and `.env.example` for every
  pair (root and backend), checked bidirectionally so neither the runtime
  file nor the committed reference rots silently

```bash
# =============================================================================
# Backend environment — copy to .env and adjust as needed.
# =============================================================================

# --- Database ---
# Async PostgreSQL connection string (local dev: localhost)
DATABASE_URL = postgresql+asyncpg://app:app@localhost:25432/app

# --- App ---
APP_NAME = "Awesome API"
```

Machine-checked by `check-environment.ts` (check 2 — section comments +
alignment; check 4 — `.env` ↔ `.env.example` key, section, per-variable comment,
**and value** pair sync).

### A Pair Carries One Set of Values

`.env.example` is a **copy** of its `.env`, not a variant: same keys, same
sections, same comments, **same values**. The one exception is a credential
(`SECRET`/`PASSWORD`/`TOKEN` in the name), where the committed reference holds a
placeholder on purpose — matched by name, so a new credential is covered the day
it is added.

When an environment really needs different values, it gets **its own file**
(`.env.local`, `.env.dev`), never a silent divergence inside one pair. Measured
reason for the check: `ALLOWED_HOSTS` gained a host in `backend/.env` while
`.env.example` kept the old list, and every other check passed — keys, sections
and comments were untouched, so nothing looked wrong.

### Root ↔ Backend Sync

`APP_NAME`, `ADMIN_EMAIL`, `ITEMS_PER_USER` exist in **both** the root `.env`
(docker-compose) and `backend/.env` (Pydantic settings). Their values **must
match** — docker-compose passes the root value into the container, so a
mismatch makes Docker (`make up`) and local (`cd backend && make dev`) runs
diverge silently. Machine-checked by `check-environment.ts`.

Beyond those three shared values, **every key that appears in both** the root
`.env` and `backend/.env` (currently `ENV`, `DATABASE_URL`, `REDIS_URL`,
`SECRET_KEY`, `APP_NAME`, `ADMIN_EMAIL`, `ITEMS_PER_USER`) must carry the
**same preceding comment line**. `ENV` is the one intentional value mismatch
(container vs local); its comment still matches. Machine-checked by
`check-environment.ts` (root ↔ backend common-key comment parity).

### Root ⊇ Backend Keys

Every key in `backend/.env` must also exist in `root/.env`. docker-compose
passes root values into the backend container; a backend-only key means the
container silently falls back to a `settings.py` default instead of the
configured value, so Docker and local runs diverge. Root-only keys are expected
(infra vars like `POSTGRES_*`, `PHOENIX_SQL_DATABASE_SCHEMA`, the host ports,
and backend settings that keep a `settings.py` default such as `CORS_ORIGINS`,
`ACCESS_TOKEN_EXPIRE_MINUTES`, `ALGORITHM`). A new backend setting only has to
be added to `root .env`/`.env.example` — `env_file` carries it into the
container with no compose edit at all.
Machine-checked by `check-environment.ts` (root ⊇ backend key invariant).

### Shared Variable Order + Comments

The variables that exist in both files (`ENV`, `DATABASE_URL`, `APP_NAME`,
`ADMIN_EMAIL`, `ITEMS_PER_USER`) must appear in the **same relative order**
and carry the **same comment line** in root `.env` and `backend/.env`:

```text
ENV → DATABASE_URL → APP_NAME → ADMIN_EMAIL → ITEMS_PER_USER
```

A reorder or a comment drift between the two files makes them hard to diff.
Machine-checked by `check-environment.ts` (check 6 — order + comments).

### Required Variables

| Variable | Type | Default | Description |
|---|---|---|---|
| `ENV` | `str` | `local` | Environment: `local` or `production` |
| `DATABASE_URL` | `str` | — | PostgreSQL connection string (async) |
| `ADMIN_EMAIL` | `str` | — | Admin contact email |
| `ITEMS_PER_USER` | `int` | `50` | Default items limit per user |
| `APP_NAME` | `str` | `Fast API Standard` | Application display name |

### SQLAlchemy Connection String Format

```
postgresql+asyncpg://user:password@host:port/dbname
```

For Alembic migrations, `DATABASE_URL` must be present in `.env`.

## Pydantic Settings (`backend/app/core/settings.py`)

```python
class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    env: str = "local"
    database_url: str
    app_name: str = "Fast API Standard"
    admin_email: str
    items_per_user: int = 50
```

Settings are loaded automatically from `.env` via Pydantic `BaseSettings`.
No manual parsing required.

## Environment Modes

| Mode | Behavior |
|---|---|
| `local` | Standard settings, debug mode |
| `production` | Production settings |

## Validation (Post-Hook)

The `check-environment.ts` post-hook validates the env contract after
tool execution:

1. `backend/.env` (or `.env.example`) defines the required variables
2. `backend/.env` and `.env.example` carry the root-style format (header
   banner, `# --- <Section> ---` markers, aligned `KEY = value` form)
3. `settings.py` declares the matching fields
4. Root ↔ backend shared variables (`APP_NAME`/`ADMIN_EMAIL`/`ITEMS_PER_USER`)
   match between root `.env` and `backend/.env`
5. Every key common to root `.env` and `backend/.env` carries the same preceding
   comment line. Values are compared only for the shared three (check 4): the
   rest legitimately differ because the container and a local run address
   different hosts — `ENV` (production/local), `DATABASE_URL` and `REDIS_URL`
   (compose service names vs localhost), `SECRET_KEY` (placeholder vs dev key)
6. Every `backend/.env` key also exists in `root/.env` — docker-compose passes
   root values into the container, so a backend-only key silently falls back
7. `.env` ↔ `.env.example` expose the same keys, the same
   `# --- <Section> ---` markers, and the same per-variable preceding
   comment for every pair (root and backend), checked bidirectionally
8. `docker-compose.yml` wires the backend through `env_file: [.env]` and carries
   no `environment:` block for it; every other service's values are `${VAR}`
   references that root `.env` defines
9. Shared variables appear in the same order and with the same comments in
   root `.env` and `backend/.env`

**AST rules** (`.omp/ast-grep/rules/environment/`, run by the same hook) add
structural checks for hardcoded env access:

| Rule | Checks |
|---|---|
| `os-environ-direct.yml` | no `os.environ[...]` / `os.getenv(...)` direct use — use `settings.py` |
| `hardcoded-connection.yml` | no literal `postgresql+asyncpg://` connection strings |
| `hardcoded-port.yml` | no literal `localhost:<port>` service ports |

## settings.env Is Not an Authorization Input

`settings.env` says **where** the code runs, never **who** may do what. A
security path that branches on it is a different program in every environment,
so the version that is tested is not the version that runs - and the weaker
branch is the one a misconfigured `ENV` makes reachable in production.

`ast-grep/rules/env-security/env-branch.yml` runs against `core/security.py`,
`dependencies/auth.py`, `routers/auth.py` and `alembic/versions/`. Decide from an
explicit setting instead (`settings.seed_api_actor` is the pattern).

## Required Security Variables

`ALLOWED_HOSTS` joins `SECRET_KEY` and `DATABASE_URL` as a variable with no
default: the app must not boot with an open Host allowlist. It lives in all four
env files and is passed through `docker-compose.yml`; `testserver` is included
locally because that is the Host Starlette's `TestClient` sends.

## Never Do These

- Commit `backend/.env` with real credentials (use `.env.example` instead)
- Hardcode environment variables in code — use `settings.py`
  (machine-checked by `check-environment.ts` AST rules:
  `os.environ`/`os.getenv` direct use, literal `postgresql+asyncpg://`
  strings, and literal service ports are all flagged)
- List backend environment keys one by one in `docker-compose.yml` — map the
  root `.env` with `env_file` instead, or the next setting nobody remembers is
  a setting the container silently does not have
  (machine-checked by `check-environment.ts`, "docker-compose.yml env wiring")
- Hardcode a non-backend service's environment value in `docker-compose.yml` —
  use `${VAR}` references resolved from root `.env`
  (machine-checked by `check-environment.ts`, "docker-compose.yml env wiring")
- Drop the section comments (`# ===` banner / `# --- <Section> ---`) from an
  env file — bare variable dumps are hard to maintain
  (machine-checked by `check-environment.ts`, "Section comments + alignment")
- Use unaligned assignments (`KEY=value`, `KEY =value`, `KEY= value`) — the
  `KEY = value` form is required
  (machine-checked by `check-environment.ts`, "Section comments + alignment")
- Add a key to `backend/.env` that is absent from `root/.env` — docker-compose
  cannot pass it to the container, so Docker runs on a `settings.py` default
  instead of the configured value
  (machine-checked by `check-environment.ts`, "Root ↔ backend shared variable sync")
- Let `.env` and `.env.example` drift (keys, `# --- <Section> ---` markers, or
  per-variable comments) for either pair — the runtime file and the
  committed reference must stay in sync bidirectionally
  (machine-checked by `check-environment.ts`, ".env ↔ .env.example pair sync")
- Reorder shared variables or rewrite their comments in one env file only —
  root `.env` and `backend/.env` must keep the same order and comments
  (machine-checked by `check-environment.ts`, "Shared variable order + comments sync")
- Forget `DATABASE_URL` when running migrations
- Use `settings.env != "production"` for security decisions — validate at runtime
