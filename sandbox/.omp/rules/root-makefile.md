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
| `make verify-fast` | `make -C backend verify-fast` | Fast iteration gate — backend only, no coverage; finish requires `make verify` |
| `make clean` | `make -C backend clean` + `make -C frontend clean` | Remove backend and frontend caches |
| `make docker-clean` | `docker compose down -v` | Stop services and remove volumes (data loss!) |
| `make verify` | `check-backend-domain + check-backend-migrations + check-backend-table-design + check-backend-auth + check-backend-exceptions + check-backend-api-http + check-backend-router-params + check-backend-naming + check-backend-transaction + check-backend-batch + check-backend-tests + check-backend-middleware + check-backend-app-setup + check-backend-core-config + check-backend-rate-limit + check-backend-background-tasks + check-backend-ownership + check-backend-audit-log + check-backend-redis-cache + check-backend-file-upload + check-backend-sse + check-backend-api-keys + check-backend-integration + check-backend-integration-configuration + check-environment + check-code-layout + check-tooling + check-frontend-code + check-ast-rules + check-omp-types + check-omp-hooks + check-omp-rules + check-omp-skills + check-makefiles + check-decks-sync + check-verify` | Run all OMP hooks + backend + frontend verify (hermetic — no running stack needed) |
| `make check-verify` | `node .omp/hooks/post/check-verify.ts` | Run backend + frontend verify (lint, typecheck, test/build) |
| `make check-backend-domain` | `node .omp/hooks/post/check-backend-domain.ts` | Check backend CRUD domain structure |
| `make check-backend-migrations` | `node .omp/hooks/post/check-backend-migrations.ts` | Check ORM ↔ DB sync (alembic check) |
| `make check-backend-table-design` | `node .omp/hooks/post/check-backend-table-design.ts` | Check backend table design invariants (1NF, keys, constraints) |
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
| `make check-code-layout` | `node .omp/hooks/post/check-code-layout.ts` | Check code layout (comments, banners, constants, member order) |
| `make check-tooling` | `node .omp/hooks/post/check-tooling.ts` | Check tooling language policy (TypeScript hooks, no Python scripts) |
| `make check-frontend-code` | `node .omp/hooks/post/check-frontend-code.ts` | Check frontend code conventions |
| `make check-ast-rules` | `node .omp/hooks/post/check-ast-rules.ts` | Prove every ast-grep rule fires (valid/invalid cases) |
| `make check-omp-types` | `node .omp/hooks/post/check-omp-types.ts` | Type-check the harness TypeScript (`.omp/**/*.ts`) |
| `make check-omp-hooks` | `node .omp/hooks/post/check-omp-hooks.ts` | Check OMP hooks directory sync |
| `make check-omp-rules` | `node .omp/hooks/post/check-omp-rules.ts` | Verify .omp/rules/ sync |
| `make check-omp-skills` | `node .omp/hooks/post/check-omp-skills.ts` | Check skills catalog ↔ discovered `SKILL.md` files |
| `make check-makefiles` | `node .omp/hooks/post/check-makefiles.ts` | Check Makefile targets consistency |
| `make check-decks-sync` | `node .omp/hooks/post/check-decks-sync.ts` | Check decks mention all rules/hooks/AST dirs |
| `make check-api-flow` | `node .omp/hooks/lib/backend-api-flow.ts` | Run every `api/*.http` against the running stack (proves state neutrality) |
| `make continuity-selftest` | `node .omp/extensions/continuity/selftest.ts` | Drive the continuity extension against a fake host |
| `make continuity-report` | `node .omp/extensions/continuity/report.ts` | Report whether continuity interventions broke their loops |
| `make hook-report` | `node .omp/hooks/lib/hook-metrics.ts` | Report what the post hooks cost per run and which ones never warned |
| `make check-api-flow-verbose` | `node .omp/hooks/lib/backend-api-flow.ts --verbose` | Same, printing every block's declared vs actual status |
| `make probe-external-api` | `node .omp/hooks/lib/backend-external-api-probe.ts` | Measure a provider before integrating it — `url='…/{start}/{end}'`, optional `filter=`, `since=`, `root=` |

## Service Stack

From `docker-compose.yml`:

| Service | Purpose | Port |
|---|---|---|
| `backend` | FastAPI app (uvicorn) | :18000 |
| `postgres` | PostgreSQL 17 | :15432 |
| `redis` | Redis 7 | :16379 |
| `frontend` | Nginx reverse proxy | :15173 |
| `phoenix` | Phoenix APM | :16006 |

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

1. **Local development**: `cd backend && make dev` (uvicorn :18000)
2. **Docker development**: `make up` (full stack on :15173)
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

- **Root `.env`** (or `.env.example`) — docker-compose only: `POSTGRES_*`, `PHOENIX_SQL_DATABASE_SCHEMA`, plus `APP_NAME`/`ADMIN_EMAIL`/`ITEMS_PER_USER` passed to the backend container via `docker-compose.yml`. Service ports are fixed in `docker-compose.yml` (15432/16379/16006/14317/18000/15173) — no port variables.
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
