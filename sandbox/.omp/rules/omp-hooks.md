---
description: OMP hook conventions - pre/post hooks, denylist, event listeners, rule update workflow
globs:
      - .omp/hooks/**/*.ts
alwaysApply: false
---

# OMP Hooks

## Rule ↔ Hook Mapping

**Project governance contract — not an OMP runtime requirement.** OMP discovers
rules and hooks as separate capabilities. This repository additionally requires
every rule in `.omp/rules/` to map to at least one enforcing hook and every
hook to map back to at least one rule. This table is the single source of truth;
`check-omp-hooks.ts` validates it mechanically.

**Separation principle** — each rule maps to at least one enforcing hook. Post
hooks stay within one validation domain; explicitly cross-cutting hooks and pre
hooks may serve several rules. Do not merge unrelated checks merely to reduce
file count.

- A domain rule normally maps to one post hook and one lib module when
  cross-file checks are needed.
- Cross-cutting hooks (`check-makefiles`, `check-verify`, `check-omp-*`) and
  `strict-*` pre hooks may be shared by multiple rules.
- When a new concern is not cross-cutting, split a new rule and hook pair.
- Example: `backend-domain.md` → `check-backend-domain.ts` →
  `lib/backend-domain-structure.ts` → `ast-grep/rules/model/`

**lib module naming** — lib modules are prefixed by their scope so backend and
frontend checks never collide:

| Prefix | Scope | Example |
|---|---|---|
| `backend-` | Backend checks | `lib/backend-domain-structure.ts`, `lib/backend-auth.ts` |
| `frontend-` | Frontend checks | `lib/frontend-code.ts` (future) |
| `hook-` | Cross-cutting guard shared by every hook | `lib/hook-safety-guard.ts`, `lib/hook-dormancy.ts`, `lib/hook-visibility.ts`, `lib/hook-metrics.ts` |
| *(none)* | Shared runner | `lib/ast-rules.ts` (scope-agnostic) |

A lib module name mirrors its rule: `backend-domain.md` →
`lib/backend-domain-structure.ts` (rule name + `-structure` for the 5-layer
checks).

A lib is normally imported by its hook. One exception is documented rather than
guessed at: `lib/backend-api-flow.ts` is **CLI-only** (`make check-api-flow`).
It executes `api/*.http` against the running stack, so it writes to the database
and calls external APIs — work that must be asked for, never triggered by a
post hook after every edit.

| Rule (`.omp/rules/`) | Pre Hook | Post Hook |
|---|---|---|
| `backend-domain.md` | `strict-backend-app-structure.ts` | `check-backend-domain.ts` |
| `backend-auth.md` | — | `check-backend-auth.ts` |
| `backend-exceptions.md` | — | `check-backend-exceptions.ts` |
| `backend-api-http.md` | — | `check-backend-api-http.ts` |
| `backend-router-params.md` | — | `check-backend-router-params.ts` |
| `backend-naming.md` | — | `check-backend-naming.ts` |
| `backend-transaction.md` | — | `check-backend-transaction.ts` |
| `backend-migrations.md` | `strict-backend-migrations.ts` | `check-backend-migrations.ts` — ORM/DB sync, one-table unpushed revisions, and upstream immutability |
| `backend-table-design.md` | — | `check-backend-table-design.ts` |
| `backend-batch.md` | — | `check-backend-batch.ts` |
| `backend-testing.md` | — | `check-backend-tests.ts` |
| `backend-middleware.md` | — | `check-backend-middleware.ts` |
| `backend-app-setup.md` | — | `check-backend-app-setup.ts` |
| `backend-core-config.md` | — | `check-backend-core-config.ts` |
| `backend-rate-limit.md` | — | `check-backend-rate-limit.ts` |
| `backend-background-tasks.md` | — | `check-backend-background-tasks.ts` |
| `backend-ownership.md` | — | `check-backend-ownership.ts` |
| `backend-audit-log.md` | — | `check-backend-audit-log.ts` |
| `backend-redis-cache.md` | — | `check-backend-redis-cache.ts` |
| `backend-file-upload.md` | — | `check-backend-file-upload.ts` |
| `backend-sse.md` | — | `check-backend-sse.ts` |
| `backend-api-keys.md` | — | `check-backend-api-keys.ts` |
| `backend-integration.md` | — | `check-backend-integration.ts` |
| `backend-integration-configuration.md` | — | `check-backend-integration-configuration.ts` |
| `environment.md` | — | `check-environment.ts` |
| `backend-code-conventions.md` | — | `check-verify.ts` (runs the configured toolchain — lint/typecheck/test) |
| `backend-makefile.md` | `strict-command-routing.ts` | `check-makefiles.ts` |
| `root-makefile.md` | `strict-command-routing.ts` | `check-makefiles.ts` |
| `root-git-workflow.md` | `strict-verified-git.ts` | — |
| `frontend-makefile.md` | `strict-command-routing.ts` | `check-makefiles.ts` |
| `frontend-code-conventions.md` | — | `check-frontend-code.ts` |
| `code-layout.md` | — | `check-code-layout.ts` |
| `tooling.md` | `strict-tooling.ts` | `check-tooling.ts` + `check-omp-types.ts` (its TypeScript type-checks) |
| `omp-conventions.md` | — | `check-omp-rules.ts` |
| `omp-naming-consistency.md` | — | `check-omp-rules.ts` (rule prefix↔globs) + `check-omp-hooks.ts` (hook name↔paths) |
| `omp-ast-rules.md` | — | `check-ast-rules.ts` (per-rule proof) + `check-omp-hooks.ts` (rule↔hook contract, declared ownership) |
| `omp-hooks.md` | — | `check-omp-hooks.ts` |
| `omp-skills.md` | — | `check-omp-skills.ts` |
| `decks-sync.md` | — | `check-decks-sync.ts` |
| `RULES.md` (sticky) | `strict-no-subagents.ts` | — |
| `RULES.md` (sticky) | `strict-additive-writes.ts` | — |
| `RULES.md` (sticky) | `strict-no-vcs-publish.ts` | — |
| `RULES.md` (sticky) | `strict-no-harness-edit.ts` | — |
| `backend-app-forbidden-tokens.md` (TTSR trigger) | — | `check-backend-exceptions.ts` + `check-environment.ts` |
| `backend-service-boundary-tokens.md` (TTSR trigger) | — | `check-backend-transaction.ts` + `check-backend-sse.ts` + `check-backend-background-tasks.ts` + `check-backend-integration.ts` |
| `backend-router-wiring-tokens.md` (TTSR trigger) | — | `check-backend-auth.ts` |
| `backend-identity-tokens.md` (TTSR trigger) | — | `check-backend-auth.ts` |
| `omp-hook-crash-guard.md` (TTSR trigger) | — | `check-omp-hooks.ts` |

**Project contract:** every rule file must appear in this table (≥1 hook), and
every hook file must appear in this table (≥1 rule). Orphans on either side are
violations.

**TTSR trigger rules** carry a regex `condition` instead of `globs`, so they are
bucketed out of the rulebook and injected at the moment a matching edit is
being streamed (see *Rule Delivery* below). They add no validation domain: each
one maps to the post hook that already owns the invariant, and that hook is
therefore exempt from the one-domain-per-hook split heuristic.

Every trigger is built the same way, and `check-omp-rules` proves it:

| Contract | Failure it prevents |
|---|---|
| `condition` is a quoted string and compiles as a regex | The runtime drops an invalid pattern with a log line nobody reads |
| `scope` is declared | The default also watches assistant prose, so *writing about* a token interrupts the turn |
| `interruptMode` is declared | The machine-global default decides whether an edit is aborted |
| Every ≥4-character identifier in `condition` appears in the body | The injected text does not explain the token that stopped the edit |
| A `## Enforcement` section names the hook that owns the invariant | A trigger becomes a second, undocumented source of truth |
| The condition matches **nothing** in the files its `scope` selects | Rewriting a legitimate line interrupts the turn (a comment naming the banned construct is the usual culprit) |

**Splitting workflow** (when a rule/hook grows beyond one domain):

1. Identify the new validation domain (e.g. auth, naming, transactions)
2. Create the rule file `<scope>-<name>.md` with its own globs
3. Create the post hook `check-<scope>-<name>.ts` (orchestrator pattern:
   AST rules + lib module calls only)
4. Move the domain's checks into `lib/<scope>-<name>.ts` (pure functions,
   scope-prefixed: `backend-`/`frontend-`)
5. Register the Makefile target + add the mapping table row
6. Run `make verify` — the split must not change behavior (all checks still pass)

## AST Rule Contract

Structural code checks that string matching cannot express precisely (function
signatures, async-ness, naming conventions) are written as **ast-grep rules**
in `.omp/ast-grep/rules/<scope>/` and executed by post hooks via the shared runner
`.omp/hooks/lib/ast-rules.ts` (`runAstRules`).

| Rule dir | Rule files | Executed by |
|---|---|---|
| `.omp/ast-grep/rules/domain/` | `service-method-async.yml`, `repository-method-uuid-param.yml`, `service-transaction-write-only.yml` | `check-backend-transaction.ts` (services/repositories) |
| `.omp/ast-grep/rules/router/` | `write-auth.yml`, `inline-depends.yml`, `response-model.yml`, `auth-all.yml` | `check-backend-auth.ts` (scans routers/) |
| `.omp/ast-grep/rules/model/` | `id-standard.yml`, `field-mapped-pattern.yml` | `check-backend-domain.ts` (scans models/) |
| `.omp/ast-grep/rules/integration/` | `timeout-configured.yml` | `check-backend-integration.ts` (scans core/integration.py) |
| `.omp/ast-grep/rules/exceptions/` | `builtin-forbidden.yml`, `http-exception-forbidden.yml`, `instance-raise.yml` | `check-backend-exceptions.ts` (scans app/) |
| `.omp/ast-grep/rules/service/` | `repository-param.yml` | `check-backend-auth.ts` (scans services/) |
| `.omp/ast-grep/rules/naming/` | `var-name.yml`, `repository-access.yml`, `inner-function-underscore.yml` | `check-backend-naming.ts` (scans app service/repository/router/batch code) |
| `.omp/ast-grep/rules/transaction/` | `service-only.yml` | `check-backend-transaction.ts` (scans non-service dirs) |
| `.omp/ast-grep/rules/conventions/` | `current-user-router-only.yml` | `check-backend-auth.ts` (scans backend app code) |
| `.omp/ast-grep/rules/batch/` | `job-async.yml`, `service-constructor.yml`, `session-from-engine.yml` | `check-backend-batch.ts` |
| `.omp/ast-grep/rules/environment/` | `os-environ-direct.yml`, `hardcoded-connection.yml`, `hardcoded-port.yml` | `check-environment.ts` |
| `.omp/ast-grep/rules/sse/` | `streaming-response.yml` | `check-backend-sse.ts` |
| `.omp/ast-grep/rules/background/` | `create-task.yml` | `check-backend-background-tasks.ts` |
| `.omp/ast-grep/rules/upload/` | `no-size-guard.yml` | `check-backend-file-upload.ts` |
| `.omp/ast-grep/rules/ownership/` | `check-missing.yml` | `check-backend-ownership.ts` |
| `.omp/ast-grep/rules/audit/` | `exposes-secret.yml` | `check-backend-audit-log.ts` |
| `.omp/ast-grep/rules/cache/` | `no-ttl.yml` | `check-backend-redis-cache.ts` |
| `.omp/ast-grep/rules/layering/` | `repository-import.yml` | `check-backend-domain.ts` (scans routers/) |
| `.omp/ast-grep/rules/factory/` | `from-session.yml` | `check-backend-domain.ts` (scans app/) |
| `.omp/ast-grep/rules/auth/` | `system-actor.yml` | `check-backend-auth.ts` (scans routers/, services/) |
| `.omp/ast-grep/rules/ownership-router/` | `router-check.yml` | `check-backend-ownership.ts` (scans routers/) |
| `.omp/ast-grep/rules/audit-readonly/` | `write-endpoint.yml` | `check-backend-audit-log.ts` (scans routers/audit.py) |
| `.omp/ast-grep/rules/logging/` | `secret-in-log.yml` | `check-backend-middleware.ts` (scans app/) |
| `.omp/ast-grep/rules/offload/` | `password-hash.yml` | `check-backend-auth.ts` (scans routers/, services/) |
| `.omp/ast-grep/rules/env-security/` | `env-branch.yml` | `check-environment.ts` (scans security modules + migrations) |

**Contract** (validated by `check-omp-hooks.ts`):

- Every rule YAML under `.omp/ast-grep/rules/` is referenced by **exactly one** post hook
- Every post hook importing `../lib/ast-rules.ts` references **≥1** rule directory
- Rule semantics: a **match is a violation** (negative rules, default) unless
  the rule declares `expect: present`, in which case **absence of a match is
  the violation** (positive rules like `Service(session)` presence)
- When ast-grep is unavailable, `runAstRules` returns `[]` — hooks degrade to
  their string checks (graceful degradation, never a false positive)

## Directory Structure

```
.omp/hooks/
+-- pre/
| +-- strict-command-routing.ts      # Cross-cutting: blocks direct tool invocations (make/bash/docker)
| +-- strict-backend-migrations.ts    # Backend: blocks edits only to upstream migration files
| +-- strict-no-subagents.ts        # Cross-cutting: blocks task (subagent) creation
| +-- strict-verified-git.ts        # Cross-cutting: runs make verify before Git commit/push
| +-- strict-no-vcs-publish.ts      # Cross-cutting: denies git commit/push — VCS belongs to the user (RULES.md)
| +-- strict-no-harness-edit.ts     # Cross-cutting: denies edits to `.omp/` — the subject cannot change the checks that grade it (2026-08-29 실측)
| +-- strict-additive-writes.ts # Backend: blocks writes outside the documented backend/ structure (new dirs under app/, stray app-root files, non-standard backend/ dirs)
| +-- strict-backend-app-structure.ts # Backend: blocks writes outside the documented backend/ structure (new dirs under app/, stray app-root files, non-standard backend/ dirs)
| +-- strict-tooling.ts            # Cross-cutting: blocks Python/shell tooling and root script dirs outside .omp/hooks/
+-- post/
  +-- check-backend-domain.ts      # Read-only: validates 5-layer CRUD domain pattern
  +-- check-backend-migrations.ts  # Read-only: validates ORM ↔ DB sync and migration scope
  +-- check-backend-table-design.ts # Read-only: validates table design invariants (1NF, keys, constraints)
  +-- check-backend-auth.ts        # Read-only: validates auth + domain exceptions
  +-- check-backend-exceptions.ts  # Read-only: validates the core exception policy (raise/handler/body)
  +-- check-backend-api-http.ts    # Read-only: validates api/*.http structure + runnable sequencing
  +-- check-backend-router-params.ts # Read-only: validates router parameter kinds, UUID ids, pagination aliases
  +-- check-backend-naming.ts      # Read-only: validates naming conventions
  +-- check-backend-transaction.ts # Read-only: validates transaction placement
  +-- check-backend-batch.ts       # Read-only: validates batch job conventions
  +-- check-backend-tests.ts       # Read-only: validates test standard (per-domain, 10 cases, auth, conftest)
  +-- check-backend-middleware.ts   # Read-only: validates CORS/security headers/request ID/logging
  +-- check-backend-app-setup.ts   # Read-only: validates health/OpenAPI metadata/API versioning
  +-- check-backend-core-config.ts # Read-only: validates settings validators/DB pool/error schema
  +-- check-backend-rate-limit.ts  # Read-only: validates slowapi limiter on login/signup
  +-- check-backend-background-tasks.ts # Read-only: validates BackgroundTasks usage
  +-- check-backend-ownership.ts   # Read-only: validates created_by ownership checks
  +-- check-backend-audit-log.ts   # Read-only: validates read-only audit endpoint
  +-- check-backend-redis-cache.ts # Read-only: validates TTL + invalidation
  +-- check-backend-file-upload.ts # Read-only: validates UploadFile size/content-type guards
  +-- check-backend-sse.ts         # Read-only: validates EventSourceResponse usage
  +-- check-backend-api-keys.ts    # Read-only: validates X-API-Key dependency
  +-- check-backend-integration.ts  # Read-only: validates external API integration contract
  +-- check-backend-integration-configuration.ts # Read-only: validates database-managed integration configuration
  +-- check-environment.ts       # Read-only: validates .env + settings.py + root↔backend sync
  +-- check-frontend-code.ts       # Read-only: validates frontend code conventions
  +-- check-code-layout.ts        # Read-only: validates comments, banners, constant placement, class member order (all code)
  +-- check-tooling.ts            # Read-only: validates the tooling language policy (TypeScript hooks, no Python scripts)
  +-- check-makefiles.ts           # Read-only: Makefile targets consistency check
  +-- check-decks-sync.ts          # Read-only: decks mention all rules/hooks/AST dirs
  +-- check-ast-rules.ts           # Read-only: proves every ast-grep rule fires (valid/invalid cases)
  +-- check-omp-types.ts           # Read-only: tsc --noEmit over .omp/tsconfig.json
  +-- check-omp-hooks.ts           # Read-only: omp-hooks.md directory structure sync
  +-- check-omp-rules.ts           # Read-only: AGENTS.md rule file sync validation
  +-- check-omp-skills.ts          # Read-only: validates skills catalog ↔ SKILL.md discovery
  +-- check-verify.ts              # Read-only: backend/frontend verify Makefile integration
```

## Naming Convention

All hooks follow a strict naming convention:

|Type|Prefix|Directory|Pattern|Examples|
|---|---|---|---|---|
|**Pre hooks**\|`strict-`\|`.omp/hooks/pre/`\|`strict-<scope>-<name>.ts`\|`strict-command-routing.ts` (all projects), `strict-backend-migrations.ts`, `strict-no-subagents.ts`, `strict-backend-app-structure.ts`|
|**Post hooks**\|`check-`\|`.omp/hooks/post/`\|`check-<scope>-<name>.ts`\|`check-backend-domain.ts`, `check-backend-tests.ts`, `check-makefiles.ts` (all scopes), `check-omp-hooks.ts`, `check-omp-rules.ts`, `check-verify.ts`|

Pre hooks use `strict-<scope>-<name>.ts` — omit `<scope>` when cross-cutting across all projects.
Post hooks use `check-<scope>-<name>.ts` — omit `<scope>` when covering all domains.

**The prefix is machine-checked, not stylistic.** Every post-hook contract check
in `check-omp-hooks` is keyed by `check-`, so `post/foo.ts` would be validated by
nothing: no `guarded()` wrapper, no `MUTATING_TOOLS` filter, no safe warning. A
file in `post/` that does not start with `check-` (or in `pre/` without
`strict-`) is a violation on that ground alone.

### When Adding a New Hook

1. **Determine the hook type:**
   - **Pre hook** — blocks tool execution before it runs (blocking validation)
   - **Post hook** — logs issues after tool execution (read-only check)

2. **Name the file:**
   - Pre: `strict-<scope>-<name>.ts` (e.g., `strict-backend-migrations.ts`, `strict-backend-app-structure.ts`) — omit `<scope>` when cross-cutting (e.g., `strict-command-routing.ts`, `strict-no-subagents.ts`)
   - Post: `check-<scope>-<name>.ts` (e.g., `check-backend-tests.ts`) — omit `<scope>` when covering all domains (e.g., `check-makefiles.ts`, `check-verify.ts`)

3. **Create the file** — see patterns below. A post hook's `tool_result` body
   must run inside `guarded("<hook>", event, () => { ... })` (see *Crash
   Visibility*), or its first exception silently retires the whole check.

4. **Register the target and gate it** — add `check-<name>` to the root
   Makefile, add it to the `verify:` prerequisite list, and add it to both the
   target's own row and the `make verify` row in `root-makefile.md`.
   `check-makefiles` fails when a post-hook target is missing from `verify` or
   when the Makefile and the documented row disagree (see
   `root-makefile.md` → Verify Membership)

5. **Run `make check-omp-hooks`** to validate consistency (part of `make verify`)

## Pre-Hooks

Blocking hooks that listen to `tool_call` events and deny specific tool invocations.

- Location: `.omp/hooks/pre/`
- Event: `tool_call` (필터링된 도구)
- Behavior: denylist pattern matching — first match wins. Patterns are anchored to a command boundary (line start, or after `&&` / `||` / `;` / `|` / `(`, optional `sudo`), allowing whitespace-free relative-path prefixes (`backend/`, `./`) but never an argument word — so `ls backend/.venv/bin/ruff` is not treated as an invocation.

For hooks that block an arbitrary tool (like `task`), block the tool name
unconditionally. A finite `agent` allowlist is unsafe because omitted,
default, or future agent types bypass it:

```ts
export default function strictNoSubagents(pi: ExtensionAPI): void {
  pi.on("tool_call", (event) => {
    if (event.toolName !== "task") return;
    return {
      block: true,
      reason: "서브에이전트 생성 금지",
    };
  });
}
```

To add/remove rules: modify the denylist array or tool check logic. No other logic changes needed.

## Post-Hooks

Read-only hooks that listen to `tool_result` events. Never block tool calls.

- Location: `.omp/hooks/post/`
- Event: `tool_result`
- Behavior: eligible mutating tool results run a read-only sync check and log
  issues via `console.error`; read-only tools are skipped. `check-verify`
  additionally skips explicit `make` commands so their diagnostics stay visible.
- Validation: `make verify` (or the individual `make check-*` targets) runs
  the same checks on demand via CLI.

### Post-Hook Validation Scope

Each post hook owns a single concern and runs after eligible mutating tools.
`check-omp-hooks.ts` requires every post hook to appear in this table: a hook
whose checks are undocumented cannot be reviewed, and five hooks had already
drifted out of it.

|Hook File|Validates|Checks|
|---|---|---|
|`check-backend-domain.ts`|5-layer CRUD pattern across `backend/app/`|Model files ↔ schemas/repositories/services/routers pairs; model `Base`/`AuditMixin`/`id`/`name`/`description`; 6 Pydantic classes + per-class `extra="forbid"` + Read `from_attributes` + Read `version: int`; service never assigns `updated_at`; 7 repository methods; service `session.begin()` + `NotFoundError`; 5 REST endpoints; `Annotated[T, Depends(factory)]` DI; router in `main.py`; model in `alembic/env.py`|
|`check-backend-table-design.ts`|Table design invariants in `backend/app/models/` (mapped classes **and** column-bearing mixins)|`__tablename__` present/snake/singular; primary key; `AuditMixin` inherited plus its own columns + `version_id_col`; atomicity — no numbered repeating groups (1NF); Booleans NOT NULL; `DateTime(timezone=True)`; foreign keys `_id` + `ondelete=` + `index=True`; explicit `String(n)` lengths; short type/status/mode strings carry an `IN (...)` check constraint|
|`check-backend-exceptions.ts`|Core exception policy across `backend/app/`|`ast-grep/rules/exceptions/` (no builtin raise outside a Pydantic validator, no `HTTPException` raised **or constructed**, no `raise stored_instance`); every raised class defined in `app/core/exceptions.py`; class ↔ `@app.exception_handler` both ways with a parent-handler allowance for subclasses; one handler per class; uniform body (`detail`, `code`, `request_id`) with an explicit `status_code`; `*Error` naming; third-party mappings (`StaleDataError`) declared in the allowlist|
|`check-backend-api-http.ts`|`api/*.http` structure, runnable sequencing, endpoint + external API coverage|File ↔ router both ways and location (`api/`, not `backend/api/`); structure (`### <Name> API` title, `### 전제:`, `@base`, named login block before the first token use, sections numbered 1..n with the status declared after a dash); Bearer on non-public requests (a `— 401` block omits it on purpose); one request block per `@router.<method>`; no literal UUID in a request line; CRUD sequencing (create → list → get → update → [409] → delete → [404]) with the id chained from the named create block and a dynamic create body when the model declares uniqueness; **state neutrality** — balanced `— 201` creates vs `— 200` deletes per collection, the actor contract — `auth.http` alone creates/deletes the account it logs in as, every domain file logs in as the seeded actor (`@actorUsername`/`@actorPassword`, `make db-init` named in `### 전제:`; the row comes from `57_seed_api_actor_user.py`), and seeded rows never deleted; a success-path (`— 200`) execute block per seeded integration operation; **runtime proof** — `lib/backend-api-flow.ts` and the `check-api-flow` target must exist and be wired to each other|
|`check-backend-router-params.ts`|Router parameter standard in `backend/app/routers/`|Four parameter kinds (path / `*Request` body named `data` / `*Dep` dependency / `*Query` alias) and nothing else; route template ↔ signature both ways; `*_id` path params typed `UUID` with no default; one body on writes only, none on GET/DELETE (form dependency is the documented exception); root `GET /` list reads paginated through `OffsetQuery`/`LimitQuery` (parent-scoped sub-collections exempt but must be path-scoped); `LimitQuery` declares `ge=`+`le=` and `ITEMS_PER_USER` ≤ the cap; signature order path → body → dependencies → query; routers declare no local `Annotated` alias|
|`check-backend-auth.ts`|Auth + domain exception patterns|`router/` AST rules (all endpoints authenticated, write-auth, inline `Depends`, response model), `service/` AST rules (no `HTTPException` in services), `conventions/` current-user-router-only, exception handler registration|
|`check-backend-naming.ts`|Naming + encapsulation in `backend/app/`|File/variable naming AST rules; module-private functions prefixed `_`; repository access forbidden outside its owning service|
|`check-backend-transaction.ts`|`session.begin()` placement|`transaction/service-only.yml` — bare, `self.`, and aliased (`svc.session.begin()`) forms forbidden outside services (incl. `app/batch/`); `domain/` write-only transaction rules|
|`check-backend-migrations.ts`|ORM ↔ DB sync and migration scope|`alembic check` autogenerate diff (ORM drift and DB drift); skipped silently when the database is unreachable|
|`check-backend-batch.ts`|Batch job conventions in `backend/app/batch/`|`engine` used directly; `Service(session)` constructor; `service.repository` access (never raw session); meaningful count/status return; `async def`|
|`check-backend-tests.ts`|Backend test standard in `backend/tests/`|Every CRUD model has `test_<name>.py`; each covers 10 standard API cases and asserts status 201/401/404/422; auth standard in `test_auth.py`; conftest swaps `async_session_factory` (real `get_session()`, no override)|
|`check-backend-middleware.ts`|Middleware stack in `main.py`|CORSMiddleware with `allow_origins`; security headers; `X-Request-ID`; `core/logging.py` exists|
|`check-backend-app-setup.ts`|App setup in `main.py`|`GET /health` (DB ping, 503); `FastAPI(title=...)`; routers under `/api/v1`|
|`check-backend-core-config.ts`|Core config in `app/core/`|`@field_validator` decorator in settings; `pool_size`/`max_overflow`/`pool_timeout` in `core/database.py`; `code`/`request_id` in error schema|
|`check-backend-rate-limit.ts`|Rate limiting in routers|`@limiter.limit` on login/signup; 429 + Retry-After when limiter used|
|`check-backend-background-tasks.ts`|Background tasks in routers|No raw `asyncio.create_task`; `background_tasks.add_task` when BackgroundTasks used|
|`check-backend-ownership.ts`|Ownership in services|`created_by == current_user` / ForbiddenError when service takes current_user|
|`check-backend-audit-log.ts`|Audit endpoint|`GET /audit` with created_by/updated_by; never hashed_password|
|`check-backend-redis-cache.ts`|Redis cache|Subject-scoped keys; per endpoint: `GET` sets `ttl_seconds=`, writes call `cache.invalidate()`|
|`check-backend-file-upload.ts`|File upload|`UploadFile` with max_size + content-type allowlist|
|`check-backend-sse.ts`|SSE endpoints|`EventSourceResponse` + `AsyncIterable[ServerSentEvent]` — not raw StreamingResponse|
|`check-backend-api-keys.ts`|API key auth|`X-API-Key` dependency + ServiceAccount model|
|`check-backend-integration.ts`|External API integration|`IntegrationClient` base + `httpx2.AsyncClient` + timeouts + retries + integration exceptions; `httpx2` confined to the client and its wiring|
|`check-backend-integration-configuration.ts`|Database-managed outbound integration configuration|Four tables (provider, named `integration_secret`, operation, unified `integration_field`), DB resolution, request JSON Schema, request sources, secrets resolved through the field's `secret_id` FK and never echoed, mapping as the only response contract (`response_root` absent → one record, at a page → every element; no `response_mode` column) with a page-mapping loop in the client, no `response_schema`/sparse value columns, external API contract tests (`test_integration_external_api.py`), spec fidelity (every seeded field carries `description`), and JSON/XML `response_format` decoding|
|`check-environment.ts`|Env contract (root docker-compose + backend)|Required vars (`ENV`, `DATABASE_URL`, `ADMIN_EMAIL`, `ITEMS_PER_USER`, `APP_NAME`) in `backend/.env`/`.env.example`; matching `settings.py` fields; `.env` ↔ `.env.example` key + section + per-variable comment pair sync (root + backend, bidirectional); root ↔ backend shared var value sync + common-key comment parity + root⊇backend key invariant (backend-only key → container silently uses default); `docker-compose.yml` `${VAR}` indirection; shared var order + comments; AST rules (no `os.environ`/`os.getenv`, no hardcoded connection strings/ports)|
|`check-frontend-code.ts`|Frontend code conventions in `frontend/src/`|Required files (`main.tsx`, `App.tsx`, `styles.css`); no class components; `@/` alias; `fetch` + `res.ok`; no hardcoded ports|
|`check-code-layout.ts`|Code layout across **every** code surface (backend Python incl. `scripts/`, frontend `src/` + package-root config, `decks/scripts/*.mjs`, `.omp/hooks/`)|Comments (no commented-out code, no parked-work markers, JSDoc header on every hook/lib); section banners in `backend/app` + `backend/scripts` (vocabulary, order, `Imports` first — empty `__init__.py` exempt); module constants under the `Constants` banner above the first class, and `const` never `let` in TS/JS; Python class member order (declarative config → fields → relationships → properties → `__init__` → public → private, dunders exempt); TS/JS class member order (fields → constructor → public → private); file layout (imports, constants, `export default`, then helpers)|
|`check-makefiles.ts`|Makefile target consistency (backend, frontend, root, check-verify)|`.PHONY` targets implemented; `##` documented targets in `.PHONY`; documented targets exist in Makefile; actual targets documented — compared against rule markdown tables; **verify membership** — every post-hook-backed `check-*` target is a prerequisite of `verify`, and the prerequisite list equals the `make verify` row in `root-makefile.md` (both directions)|
|`check-decks-sync.ts`|Decks ↔ harness sync (decks/harness-rules/slides.md)|Every rule file, pre/post hook, and AST rule dir is mentioned in the deck source (additive check — missing artifacts flagged)|
|`check-tooling.ts`|Tooling language policy across the tree|Python confined to `backend/app`, `backend/tests`, `backend/alembic`; the only shell script is `backend/scripts/start.sh`; `.omp/hooks/` is TypeScript only; no root `scripts/`/`tools/`/`bin/`/`utils/` directory; scripts only under `.omp/hooks/`, `frontend/`, `decks/`; every root `check-*` target runs `node .omp/hooks/...`|
|`check-omp-types.ts`|Harness TypeScript type-checks|`tsc --noEmit` over `.omp/tsconfig.json` (62 files); reports the first 3 `error TS` lines|
|`check-omp-hooks.ts`|`.omp/hooks/` ↔ `omp-hooks.md` directory-structure sync + hook functional contract + rule↔hook mapping|Every hook listed in `omp-hooks.md` exists on disk (dangling ref); every actual `.omp/hooks/**/*.ts` file is listed in `omp-hooks.md` (orphan); the file-name prefix (`post/check-*`, `pre/strict-*`) that every contract check is keyed by; post hooks must call `buildSafeWarning` + `wrapWarning` and must not implement `lastWarning`; the guard call shape — `buildSafeWarning(event.toolName, "<hook>", issues, fixHint)` with the hook's own name used in `buildSafeWarning`/`wrapWarning`/`resetSuppression` (a dropped argument used to kill the hook with `visible.map is not a function`); the crash-guard contract — `guarded` imported from `lib/hook-visibility.ts`, one wrapper counted per `pi.on("tool_result")` registration, and the name it declares equal to the file's; `lib/hook-visibility.ts` itself logs the crash, appends to the original content, and never rethrows; `MUTATING_TOOLS` filter required; pre hooks `return { block: true }` (deny execution); every rule maps to ≥1 hook and every hook to ≥1 rule|
|`check-ast-rules.ts`|Per-rule proof of the ast-grep rule set|Every rule under `.omp/ast-grep/rules/` declares an `id:` and has a case file in `.omp/ast-grep/tests/`; `ast-grep test` passes (every `invalid:` snippet matches, every `valid:` snippet does not); ast-grep itself is present — a missing binary means no structural rule ran, which is a failure, not a pass|
|`check-omp-rules.ts`|Dynamic rule-loading contract|`AGENTS.md` has no `@rules/` imports; no `rules/RULES.md` shadow; valid frontmatter (`description`, `globs`, `alwaysApply=false`); always-apply set ≤ 2|
|`check-omp-skills.ts`|`.omp/rules/omp-skills.md` ↔ `.omp/skills/` catalog|Every discovered direct-child `SKILL.md` has one catalog row; `name` matches its directory; `description`, Trigger, Verification, and Lifecycle are non-empty; Lifecycle is project metadata limited to `active` or `deprecated`|
|`check-verify.ts`|Backend + frontend verify execution|Runs `make verify` in backend/ (lint, typecheck, test) and frontend/ (lint, typecheck, build)|

### Crash Visibility

The extension runner catches a `tool_result` handler's exception, hands it to
`emitError(...)` and continues: the throw never reaches the conversation and the
handler's `{ content }` override is dropped. A hook that dies on its first tool
call therefore enforces nothing for the rest of the session while `make
check-<hook>` still passes by hand — a dead check reads exactly like a passing
one. That already happened here: a `buildSafeWarning()` call missing its
`toolName` threw from inside the safety guard, and the hook simply went quiet.

So every post hook's handler body runs inside `guarded()` from
`lib/hook-visibility.ts`:

```ts
pi.on("tool_result", (event: { toolName?: string; content?: Array<{ type: string; text?: string }> }) =>
  guarded("check-omp-rules", event, () => {
    // the check itself, unchanged
  }));
```

A throw is then reported three ways: a one-line `<system-notice>` appended to
the tool result (capped at 2 per hook + message, so a permanent crash cannot
bury the output it is attached to), an uncapped line in
`.omp/state/hook-crash.log` (gitignored, outlives the session), and stderr. The
original tool content is always preserved, and the crash is never rethrown —
one broken hook must not decide what the others get to report.

`check-omp-hooks` rejects a post hook that does not import `guarded`, or whose
`guarded()` name does not match its file name (the notice tells the reader to
re-run `make <hookName>`). Wrappers are **counted** against `pi.on("tool_result")`
registrations, so a second handler added later cannot slip in bare.

**Pre hooks are a documented exception.** `emitToolCall` turns a handler's throw
into `{ block: true }`, so a broken pre hook announces itself by refusing every
tool call it filters — loudly, immediately, and without a wrapper. Wrapping them
would mean deciding, inside the guard, whether a crashed policy hook should still
block; fail-closed is already the right answer, and a guard that could return
"allow" on a crash would be worse than no guard. The cost is a vague reason
string (`Extension <path> ...`) rather than a silent failure.

### Self-Measurement

`guarded()` is the only place that sees every post-hook run, so it also times
each one and records the outcome through `lib/hook-metrics.ts`: `quiet` (ran,
said nothing), `warned` (returned a notice), `crashed`. Snapshots are appended
to `.omp/state/hook-metrics.jsonl` (gitignored) at most every 15s, and
`make hook-report` prints the totals:

```
hook                                    runs  worked  warned  fixed  crash  totalMs  maxMs
check-code-layout                          5       5       2      1      0       19      5
43.1ms per working run
warned→fixed: 1/2 (1 still open)
rule channel: 2 guidance read(s), 1 authoring read(s), 1 paged, 1 via rule://
```

`runs` counts every invocation, `worked` only those that took ≥1ms — whether a
run was filtered out by the hook's own read-only tool guard is **not** inferred,
because each hook owns a different filter. What the report is for:

- `fixed` + `cleared` answer whether a warning worked. A finding opens on the
  **file the tool arguments named**, and closes once the hook is quiet again
  after any call that can change the tree — these checks scan the whole tree, so
  a quiet run is proof the complaint is gone. Attribution is what the two
  columns separate: `fixed` when that call named the warned file, `cleared` when
  it did not. Measured over 698 real warnings, only ~10% were answered by
  rewriting the warned file (50% by the `make check-*` the warning asked for,
  38% by a write elsewhere), so counting only `fixed` reports a permanent zero.
  Silence after a `read` proves nothing about the tree and closes nothing;
- the rule channel counts what reached the model: `rule://<name>` and
  `.omp/rules/<name>.md` are two doors onto the same body, and reads of a rule
  the same run edited are **authoring**, not guidance. Recording happens in one
  owning hook (`check-omp-rules`) because 36 hook module instances would count
  each read 36 times;
- a hook with `worked > 0` and `warned == 0` over many sessions is either
  guarding something that never breaks or checking nothing at all — the dormancy
  reason says which, and the count alone is **not** evidence of a missed
  violation;
- `totalMs`/`maxMs` turn "hooks feel slow" into a number per hook;
- `crash` is the count behind `.omp/state/hook-crash.log`.

### Rule Attribution

Every check's CLI tail calls `printRuleHint("check-<self>")` (from
`lib/hook-rule-hint.ts`) before reporting failures, so a red `make verify`
prints `Rule: rule://<name> — <description>` and the agent can read the
governing rule instead of rediscovering its requirements one failure at a
time. The check-name → rule-name mapping lives in `hook-rule-hint.ts`
(`RULE_NAME_EXCEPTIONS` for non-1:1 names, existence-verified); checks with no
governing rule are listed in `check-omp-hooks`'s `NO_RULE_CHECKS` with a
reason. `check-omp-hooks` enforces both statically.

### Warning Shape

An issue line names **where**, **what**, and **how**: `main.py: CORS missing —
add CORSMiddleware (dev origin http://localhost:15173)`. The line number belongs
there whenever the check has it (`${label}:${index + 1}: trailing whitespace`).
A warning that names no file sends the reader to grep the tree, so
`check-omp-hooks` rejects any literal `issues.push("...")` string that mentions
no file or directory.

### Dormant Checks

Seven hooks only assert something when the feature exists in the app
(rate-limit, file-upload, sse, api-keys, background-tasks, audit-log,
ownership — and redis-cache when `core/cache.py` is absent). They used to print
the same `PASS: ... standard valid` whether the code was compliant or simply
absent, so "34 checks passed" read as 34 guarded invariants when 7 were guarding
nothing.

A feature-gated hook must return `dormant("<hook>", "<why>")` from
`lib/hook-dormancy.ts` and print its banner through `passLine(...)`:

```
PASS: backend sse standard valid (dormant — no SSE endpoint in app/routers)
```

`check-omp-hooks` rejects a hook whose header claims "Optional feature" while it
never calls `dormant()`.

### Scope Resolution

Scoped hooks must reference their scope through a direct path (`backend/`,
`frontend/`, `.omp/`) or delegate through a matching scope-prefixed lib module
such as `lib/backend-integration-configuration.ts`. Prefix-less hooks are cross-cutting.

**Never construct notices or deduplication inline** — direct `lastWarning` state and manual `return { content: [...] }` paths bypass the shared content-length protection and can hide the tool result, causing an infinite loop. `check-omp-hooks.ts` rejects both patterns.

**Context economy** — two guards keep post hooks from wasting context:

1. **Tool filter**: read-only tools (`read`, `grep`, `glob`, `ask`, `todo`,
   `web_search`, `inspect_image`, …) cannot change files, so the check is
   skipped after them. Only mutating tools (`write`, `edit`, `bash`, `eval`,
   `ast_edit`, `lsp`, `browser`, `hub`, `task`) trigger the check.
2. **Shared warning guard**: at most three issue lines; long tool output gets a
   one-line notice; the same hook/issue warning is injected at most twice
   across tools and resets only when the issue set resolves.
3. **Path gate**: a hook runs only when the event touched its domain. Import
   `touchesPath` (path-bearing events only; shells pass) or `touchesStrict`
   (also reads the shell command) from `lib/hook-scope.ts` and gate right after
   the tool filter; a hook that must see everything says so with a
   `// hook-scope: global — <reason>` comment. Measured 2026-08-29: one mutating
   tool result cost 6.8s across the 36 post hooks (write) and 4.9s (bash), and
   3.3s of that was harness meta checks firing on a `backend/` edit.

```ts
const warning = buildSafeWarning(
  event.toolName,
  "check-omp-rules",
  issues,
  "run make check-omp-rules for details",
);
if (warning === null) return;
console.error(warning);
return { content: wrapWarning(warning, event.content, "check-omp-rules") };
```
- The shared guard receives hook names already prefixed with `check-`; compact
  notices must therefore direct users to `make <hookName>`, never
  `make check-<hookName>`.

## Harness Construction Guardrails

These are correctness constraints, not style preferences. `check-omp-hooks.ts`
enforces the machine-checkable parts.

1. **One policy decision source.** A pre-hook and its post-checker must import
   the same helper for lifecycle decisions. Do not duplicate upstream, path,
   revision, or command parsing in each hook.
2. **Post results preserve evidence.** Post hooks never block. Every warning
   must use `buildSafeWarning()` and `wrapWarning(warning, event.content, ...)`;
   the wrapper must append the original result before its notice.
3. **Suppress by violation, not tool.** A warning's repeat limit is keyed by
   hook and issue set. Changing from `edit` to `bash` must not restart a loop.
4. **Do not nest explicit verification.** A hook must not run a broader check
   after a user-invoked `make` command whose own output is the diagnosis.
   `check-verify` detects `event.input.command` and returns without nesting.
5. **Accept valid formatting.** Harness validators match syntax flexibly;
   formatting a handler across lines must not turn a working hook into a
   false failure.
6. **A crash is a finding, not silence.** Every post hook's `tool_result` body
   runs inside `guarded()` from `lib/hook-visibility.ts`. The runner swallows a
   raw throw, so an unwrapped handler can retire its entire rule with no trace
   in the conversation, the transcript, or the CLI.

When a new hook can affect tool execution or output, add a corresponding
negative check to `check-omp-hooks.ts` before relying on it.


### On-Demand Validation

Post hooks surface drift **immediately** after an edit; `make verify` (or individual `make check-*` targets) runs the identical checks **on demand** for a clean pre-commit signal. The CLI targets execute the hook files directly:

- `make check-backend-domain` → `node .omp/hooks/post/check-backend-domain.ts`
- `make check-backend-table-design` → `node .omp/hooks/post/check-backend-table-design.ts`
- `make check-backend-batch` → `node .omp/hooks/post/check-backend-batch.ts`
- `make check-backend-tests` → `node .omp/hooks/post/check-backend-tests.ts`
- `make check-backend-middleware` → `node .omp/hooks/post/check-backend-middleware.ts`
- `make check-backend-app-setup` → `node .omp/hooks/post/check-backend-app-setup.ts`
- `make check-backend-core-config` → `node .omp/hooks/post/check-backend-core-config.ts`
- `make check-backend-rate-limit` → `node .omp/hooks/post/check-backend-rate-limit.ts`
- `make check-backend-background-tasks` → `node .omp/hooks/post/check-backend-background-tasks.ts`
- `make check-backend-ownership` → `node .omp/hooks/post/check-backend-ownership.ts`
- `make check-backend-api-keys` → `node .omp/hooks/post/check-backend-api-keys.ts`
- `make check-backend-integration` → `node .omp/hooks/post/check-backend-integration.ts`
- `make check-backend-integration-configuration` → `node .omp/hooks/post/check-backend-integration-configuration.ts`
- `make check-environment` → `node .omp/hooks/post/check-environment.ts`
- `make check-frontend-code` → `node .omp/hooks/post/check-frontend-code.ts`
- `make check-omp-hooks` → `node .omp/hooks/post/check-omp-hooks.ts`
- `make check-omp-rules` → `node .omp/hooks/post/check-omp-rules.ts`
- `make check-omp-skills` → `node .omp/hooks/post/check-omp-skills.ts`
- `make check-makefiles` → `node .omp/hooks/post/check-makefiles.ts`
- `make check-decks-sync` → `node .omp/hooks/post/check-decks-sync.ts`
- `make check-verify` → `node .omp/hooks/post/check-verify.ts`

Each hook file guards its CLI entry with `process.argv[1]` detection — the same code path runs both inline (post-hook) and on demand.

Post-hooks perform read-only validation inline on every `tool_result` event — they are not empty stubs.

## Rule Update Workflow

When adding/updating rule files in `.omp/rules/`:

1. Edit the rule file (any tool — `write`/`edit`/`bash` all work; no pre-hook restricts `.omp/rules/`)
2. Run `make verify` (or `make check-omp-rules`) to validate the dynamic-loading contract
3. Resolve any discrepancies

## Authoring Invariants (enforced by `check-omp-hooks`)

These exist because the harness's own measurements say each class can grow. From
2,297 measured runs per hook across 56 session starts:

| Invariant | Why | Measured |
|---|---|---|
| Every post hook gates on `MUTATING_TOOLS` | a check that runs after a read spends context on a turn that changed nothing | 36/36 already comply — this holds the line |
| Every post hook declares a path scope (`touchesPath`/`touchesStrict`) or a `// hook-scope: global — <reason>` | a check that runs on events outside its domain spends the agent's wall clock, not just context | one write cost 6.8s of hook time; the meta checks in it (2.7s `check-omp-hooks`, 0.4s `check-omp-types`) had nothing to do with the edited file (2026-08-29) |
| Only `post/check-verify.ts` may execute the project gate (`make`, `pytest`, `ruff`, `pyright`, `npm`, `uv`) | the gate is 54% of all hook time (1,120s of 2,058s) and a second runner races the agent's own `make` | one owner today |
| Every `LoopKind` the continuity extension declares must be emitted by a detector | a kind nothing emits still ships in the state blob and the report vocabulary | `oscillation` was emitted but judged by nobody |
| Every declared `LoopKind` must be **driven by a self-test case** | grepping the self-test for a kind's name proves someone typed it, not that a case exercises it | measured by the run itself: `oscillation` and `errorLoop` had no case until the claim said so |

The last one is deliberately not a static check: `make continuity-selftest`
records the kinds its own cases produce and fails on any declared kind that never
fired. A threshold nobody can drive is a threshold nobody can change safely.

## Never Do These

- Run the project gate (`make verify`, `make test`, `pytest`, `ruff`, `pyright`,
  `npm run build`) from any post hook except `check-verify` — read files instead
- Declare a `LoopKind` no detector emits, or one no self-test case drives
- Put blocking logic in post hooks — they can't block tool calls
- Mix pre and post hooks in the same directory
- Reference `make verify-rules` or `scripts/verify_rules.ts` — they do not exist; use `make verify`
- Forget to keep `.omp/hooks/` and `omp-hooks.md` in sync
- Register a `tool_result` handler whose body is not wrapped in `guarded()` — the
  runner swallows the throw and the hook goes quiet for the rest of the session
