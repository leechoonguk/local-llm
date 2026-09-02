---
description: Root Makefile — docker-compose orchestration, services lifecycle
globs:
      - Makefile
      - docker-compose.yml
      - .env.example
alwaysApply: false
---

# Root Makefile Usage


## Self-Documenting Targets

Every target carries a `## <description>` on its header line. `make help` greps
those descriptions, so a target without one exists but cannot be found - and an
undiscoverable target is re-invented as a raw command. `check-makefiles`
enforces it on the root, backend, frontend and decks Makefiles.

## Verify Membership

`make verify` is the gate: `strict-verified-git` runs it before every commit
and the `commit` skill treats its exit status as authoritative. A `check-*`
target that exists but is not a prerequisite of `verify` passes when run by
hand and is never run by the gate — three such targets
(`check-backend-exceptions`, `check-backend-router-params`, `check-ast-rules`)
sat green and unexecuted for a day before anyone noticed. The contract,
enforced by `check-makefiles`:

- Every `check-<name>` target whose recipe runs `node .omp/hooks/post/...`
  **must** be a prerequisite of `verify`. Post hooks are hermetic by design, so
  there is no reason for one to stay outside the gate.
- Targets backed by `.omp/hooks/lib/` (`check-api-flow`,
  `check-api-flow-verbose`) need a running stack and write to the database;
  they stay out of `verify` and are run on request.
- The `make verify` row in the table below lists **exactly** the Makefile's
  prerequisites, joined by ` + `, in the same order. The doc is the reviewable
  contract, the Makefile is the executed one — `check-makefiles` diffs them in
  both directions, so editing one without the other fails the gate.

Adding a post hook therefore touches four places: the hook file, its
`check-<name>` target, the `verify:` prerequisite list, and this table (its own
row plus the `make verify` row).

## Overview

The root `Makefile` orchestrates the entire stack via `docker compose`.
Run from the project root.

## Makefile Targets

| Target | Command | Purpose |
|---|---|---|
| `make help` | `grep -E '^[a-zA-Z_-]+:.*?## .*'` | Show this help |
| `make build` | `docker compose build` | Build all service images |
| `make up` | `docker compose up -d --build` | Start full stack (detached) |
| `make down` | `docker compose down` | Stop and remove all containers |
| `make infra-up` | `docker compose up -d postgres redis phoenix` | Start infrastructure only |
| `make infra-down` | `docker compose down postgres redis phoenix` | Stop infrastructure only |
| `make db-init` | `docker compose down -v postgres` | Reset DB: drop, recreate, migrate |
| `make db-query` | `make -C backend migrate` + `docker compose exec -T postgres psql -c` | Run SQL at head — `make db-query q="SELECT …"` |
| `make logs` | `docker compose logs -f` | Tail logs from all services |
| `make ps` | `docker compose ps` | List running services |
| `make clean` | `make -C backend clean` + `make -C frontend clean` | Remove backend and frontend caches |
| `make docker-clean` | `docker compose down -v` | Stop services and remove volumes (data loss!) |
| `make verify` | `check-backend-domain + check-backend-contract + check-backend-migrations + check-backend-table-design + check-backend-model-files + check-backend-repository-files + check-backend-service-injection + check-backend-auth + check-backend-exceptions + check-backend-api-http + check-backend-router-params + check-backend-naming + check-backend-transaction + check-backend-batch + check-backend-tests + check-backend-middleware + check-backend-app-setup + check-backend-core-config + check-backend-rate-limit + check-backend-background-tasks + check-backend-ownership + check-backend-audit-log + check-backend-redis-cache + check-backend-file-upload + check-backend-sse + check-backend-api-keys + check-backend-integration + check-backend-integration-configuration + check-environment + check-duplicate-blocks + check-code-layout + check-tooling + check-frontend-code + check-frontend-domain + check-frontend-api-layer + check-frontend-screens + check-frontend-design + check-frontend-components + check-frontend-routing + check-frontend-contract + check-frontend-types + check-frontend-i18n + check-ast-rules + check-omp-types + check-omp-hooks + check-omp-rules + check-omp-skills + check-makefiles + check-decks-sync + check-verify` | Run all OMP hooks + backend + frontend verify (hermetic — no running stack needed) |
| `make check-verify` | `node .omp/hooks/post/check-verify.ts` | Run backend + frontend verify (lint, typecheck, test/build) |
| `make check-backend-domain` | `node .omp/hooks/post/check-backend-domain.ts` | Check backend CRUD domain structure |
| `make check-backend-contract` | `node .omp/hooks/post/check-backend-contract.ts` | Check every backend surface is reachable from an entry point |
| `make check-backend-migrations` | `node .omp/hooks/post/check-backend-migrations.ts` | Check ORM ↔ DB sync (alembic check) |
| `make check-backend-table-design` | `node .omp/hooks/post/check-backend-table-design.ts` | Check backend table design invariants (1NF, keys, constraints) |
| `make check-backend-model-files` | `node .omp/hooks/post/check-backend-model-files.ts` | Check model files — one table, one class, one file (`rule://backend-model-files`) |
| `make check-backend-repository-files` | `node .omp/hooks/post/check-backend-repository-files.ts` | Check repository files — one repository, one table, named after it (`rule://backend-repository-files`) |
| `make check-backend-service-injection` | `node .omp/hooks/post/check-backend-service-injection.ts` | Check no service imports another service (`rule://backend-service-injection`) |
| `make check-backend-auth` | `node .omp/hooks/post/check-backend-auth.ts` | Check backend auth conventions |
| `make check-backend-exceptions` | `node .omp/hooks/post/check-backend-exceptions.ts` | Check core exception policy (raise only core exceptions) |
| `make check-backend-api-http` | `node .omp/hooks/post/check-backend-api-http.ts` | Check router ↔ .http sync |
| `make check-backend-router-params` | `node .omp/hooks/post/check-backend-router-params.ts` | Check backend router parameter standard (path/body/dep/query) |
| `make check-backend-naming` | `node .omp/hooks/post/check-backend-naming.ts` | Check backend naming conventions |
| `make check-backend-transaction` | `node .omp/hooks/post/check-backend-transaction.ts` | Check backend transaction conventions |
| `make check-backend-batch` | `node .omp/hooks/post/check-backend-batch.ts` | Check backend batch job conventions |
| `make check-backend-tests` | `node .omp/hooks/post/check-backend-tests.ts` | Check backend test standard (per-domain, 10 cases, auth, conftest) |
| `make check-backend-middleware` | `node .omp/hooks/post/check-backend-middleware.ts` | Check backend middleware (CORS, security headers, request ID, logging) |
| `make check-backend-app-setup` | `node .omp/hooks/post/check-backend-app-setup.ts` | Check backend app setup (health, OpenAPI metadata, /api/v1) |
| `make check-backend-core-config` | `node .omp/hooks/post/check-backend-core-config.ts` | Check backend core config (settings validators, DB pool, error schema) |
| `make check-backend-rate-limit` | `node .omp/hooks/post/check-backend-rate-limit.ts` | Check backend rate limiting (slowapi on login/signup) |
| `make check-backend-background-tasks` | `node .omp/hooks/post/check-backend-background-tasks.ts` | Check backend background tasks (BackgroundTasks pattern) |
| `make check-backend-ownership` | `node .omp/hooks/post/check-backend-ownership.ts` | Check backend ownership checks (created_by verification) |
| `make check-backend-audit-log` | `node .omp/hooks/post/check-backend-audit-log.ts` | Check backend audit log endpoint |
| `make check-backend-redis-cache` | `node .omp/hooks/post/check-backend-redis-cache.ts` | Check backend Redis cache (TTL + invalidation) |
| `make check-backend-file-upload` | `node .omp/hooks/post/check-backend-file-upload.ts` | Check backend file upload (size + content-type guards) |
| `make check-backend-sse` | `node .omp/hooks/post/check-backend-sse.ts` | Check backend SSE (EventSourceResponse) |
| `make check-backend-api-keys` | `node .omp/hooks/post/check-backend-api-keys.ts` | Check backend API keys (X-API-Key dependency) |
| `make check-backend-integration` | `node .omp/hooks/post/check-backend-integration.ts` | Check external API integration contract |
| `make check-backend-integration-configuration` | `node .omp/hooks/post/check-backend-integration-configuration.ts` | Check database-managed integration configuration contract |
| `make check-environment` | `node .omp/hooks/post/check-environment.ts` | Check .env + settings.py + root↔backend sync |
| `make check-duplicate-blocks` | `node .omp/hooks/post/check-duplicate-blocks.ts` | Check for duplicated block runs (stale rewrite + partial edits) |
| `make check-code-layout` | `node .omp/hooks/post/check-code-layout.ts` | Check code layout (comments, banners, constants, member order) |
| `make check-tooling` | `node .omp/hooks/post/check-tooling.ts` | Check tooling language policy (TypeScript hooks, no Python scripts) |
| `make check-frontend-code` | `node .omp/hooks/post/check-frontend-code.ts` | Check frontend code conventions |
| `make check-frontend-domain` | `node .omp/hooks/post/check-frontend-domain.ts` | Check the frontend 6-layer domain pattern |
| `make check-frontend-api-layer` | `node .omp/hooks/post/check-frontend-api-layer.ts` | Check the frontend API layer (one client, keys, invalidation) |
| `make check-frontend-screens` | `node .omp/hooks/post/check-frontend-screens.ts` | Check the per-screen-type templates |
| `make check-frontend-routing` | `node .omp/hooks/post/check-frontend-routing.ts` | Check paths ↔ routes ↔ navigation and the layout guards |
| `make check-frontend-contract` | `node .omp/hooks/post/check-frontend-contract.ts` | Check frontend types/endpoints against the backend schemas/routers |
| `make check-frontend-types` | `node .omp/hooks/post/check-frontend-types.ts` | Check request/response types, nullability, optionality, verbs and query params |
| `make check-frontend-i18n` | `node .omp/hooks/post/check-frontend-i18n.ts` | Check locale parity, referenced keys and hardcoded text |
| `make check-frontend-design` | `node .omp/hooks/post/check-frontend-design.ts` | Check the design system (theme tokens, metrics, component vocabulary) |
| `make check-frontend-components` | `node .omp/hooks/post/check-frontend-components.ts` | Check component boundaries — no shape written twice (`rule://frontend-components`) |
| `make check-ast-rules` | `node .omp/hooks/post/check-ast-rules.ts` | Prove every ast-grep rule fires (valid/invalid cases) |
| `make check-omp-types` | `node .omp/hooks/post/check-omp-types.ts` | Type-check the harness TypeScript (`.omp/**/*.ts`) |
| `make check-omp-hooks` | `node .omp/hooks/post/check-omp-hooks.ts` | Check OMP hooks directory sync |
| `make check-omp-rules` | `node .omp/hooks/post/check-omp-rules.ts` | Verify .omp/rules/ sync |
| `make check-omp-skills` | `node .omp/hooks/post/check-omp-skills.ts` | Check skills catalog ↔ discovered `SKILL.md` files |
| `make check-makefiles` | `node .omp/hooks/post/check-makefiles.ts` | Check Makefile targets consistency |
| `make check-decks-sync` | `node .omp/hooks/post/check-decks-sync.ts` | Check decks mention all rules/hooks/AST dirs |
| `make check-api-flow` | `node .omp/hooks/lib/backend-api-flow.ts` | Run every `api/*.http` against the running stack (proves state neutrality) |
| `make hook-report` | `node .omp/hooks/lib/hook-metrics.ts` | Report what the post hooks cost per run and which ones never warned |
| `make check-api-flow-verbose` | `node .omp/hooks/lib/backend-api-flow.ts --verbose` | Same, printing every block's declared vs actual status |
| `make probe-external-api` | `node .omp/hooks/lib/backend-external-api-probe.ts` | Measure a provider before integrating it — `url='…/{start}/{end}'`, optional `filter=`, `since=`, `root=` |

## Service Stack

From `docker-compose.yml`. The host port is the default of an env variable
(`${BACKEND_PORT:-28000}`), so a machine that already runs one of these can move
it in the root `.env`; the container port never moves, because every in-network
URL names it.

**The project name is declared, not derived.** `docker-compose.yml` opens with
`name: fast-api-standard`, and that string prefixes every container, volume and
network (`fast-api-standard_pgdata`). Without it compose falls back to the
directory name, so renaming the checkout — or cloning it under another path —
creates a second, empty set of volumes and the database reads as wiped while
the old data sits in an orphaned volume. Measured: `make ps` from a directory
named `renamed-checkout` still reports the `fast-api-standard` containers.

This is also what keeps sibling stacks on one machine apart: another checkout
here declares `local-llm-sandbox`, so both run `postgres`/`redis`/`phoenix`
services and both declare `pgdata`/`redisdata` volumes without colliding.

| Service | Purpose | Host port (variable) |
|---|---|---|
| `backend` | FastAPI app (uvicorn) | :28000 (`BACKEND_PORT`) |
| `postgres` | PostgreSQL 17 | :25432 (`POSTGRES_PORT`) |
| `redis` | Redis 7 | :26379 (`REDIS_PORT`) |
| `frontend` | Nginx reverse proxy | :25173 (`FRONTEND_PORT`) |
| `phoenix` | Phoenix APM | :26006 (`PHOENIX_UI_PORT`), :24317 (`PHOENIX_GRPC_PORT`) |

## Workflow

1. **Start infrastructure**: `make infra-up` (postgres, redis, phoenix)
2. **Start full stack**: `make up` (backend + infra)
3. **Reset database**: `make db-init` (drops + migrates)
4. **View logs**: `make logs` (follow mode)
5. **Stop infrastructure**: `make infra-down` (keeps backend running)
6. **Stop everything**: `make down`
7. **Remove Docker services and volumes**: `make docker-clean` (data loss)

**Reading the database.** `make db-query q="SELECT …"` is the only sanctioned way
to inspect rows: it applies migrations first, so an answer is never read from a
database that is behind, and it runs `psql` inside the postgres container so no
local client and no second copy of the credentials exist. Checking state through
an API endpoint instead reads through a layer that filters, paginates and
serialises — fine for behaviour, wrong for "does this row exist".

## Development Workflow

1. **Local development**: `cd backend && make dev` (uvicorn :28000)
2. **Docker development**: `make up` (full stack on :25173)
3. **Switch**: `make down` → `make up`

## Verification Status

- A `make verify` failure is authoritative only when the command's captured exit
  status is nonzero.
- If a tool wrapper reports a nonzero status while every check prints `PASS`, rerun
  the command and capture Make's status before changing code:

  ```bash
  make verify; status=$?; printf 'MAKE_VERIFY_EXIT=%s\n' "$status"
  ```

- `MAKE_VERIFY_EXIT=0` means verification passed. Report the wrapper discrepancy
  as a harness issue; do not change project code to satisfy a contradictory status.

## Environment

Two env files, two purposes:

- **Root `.env`** (or `.env.example`) — docker-compose only: `POSTGRES_*`, `PHOENIX_SQL_DATABASE_SCHEMA`, plus `APP_NAME`/`ADMIN_EMAIL`/`ITEMS_PER_USER` passed to the backend container via `docker-compose.yml`. It also owns the **host** ports (`POSTGRES_PORT`, `REDIS_PORT`, `PHOENIX_UI_PORT`, `PHOENIX_GRPC_PORT`, `BACKEND_PORT`, `FRONTEND_PORT`), each a `${VAR:-default}` in `docker-compose.yml`; the container side never moves, because every in-network URL names it.
- **`backend/.env`** — the backend app's own settings (`ENV`, `DATABASE_URL`, `APP_NAME`, `ADMIN_EMAIL`, `ITEMS_PER_USER`), read by Pydantic settings. See `environment.md`.

## Delegation

`db-init` delegates the migration step to `make -C backend migrate`. Spelling
out `.venv/bin/alembic upgrade head` here would duplicate what that target owns
(and `environment.md` already fixes the settings source), so the root Makefile
orchestrates compose and hands backend work to the backend Makefile.

## Never Do These

- Declare a catch-all rule (`%:`, `.DEFAULT:`) in any Makefile — it answers every
  unknown target with success, so `make check-anything` passes and the whole gate
  reads green without running. Measured: an unattended local model whose armed
  acceptance was `make definitely-not-a-target` added exactly that rule to make
  the predicate pass. `check-makefiles` now rejects it, and an acceptance
  predicate should be the whole gate (`make verify`) precisely because a narrow
  one invites rewriting the gate instead of doing the work.
- `make docker-clean` in production (destroys volumes + data)
- Run `make up` without `make infra-up` first (postgres/redis won't be ready)
- Forget to run `make db-init` after pulling model changes
- Use `make up` for rapid iteration — `cd backend && make dev` is faster
