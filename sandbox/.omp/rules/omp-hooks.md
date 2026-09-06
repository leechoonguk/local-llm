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
- A hook whose name carries no scope prefix is cross-cutting, as are `strict-*`
  pre hooks; both may be shared by multiple rules. Membership follows from the
  absent prefix, not from a list of hook names.
- When a new concern is not cross-cutting, split a new rule and hook pair.
- Example: `backend-domain.md` → `check-backend-domain.ts` →
  `lib/backend-domain-structure.ts` → `ast-grep/rules/model/`

**lib module naming** — lib modules are prefixed by their scope so backend and
frontend checks never collide:

| Prefix | Scope | Example |
|---|---|---|
| `backend-` | Backend checks | `lib/backend-layout.ts` (the layer layout — one declaration for the write gate, `layerFiles()` traversal, and the meta-check), `lib/backend-domain-structure.ts`, `lib/backend-auth.ts` |
| `frontend-` | Frontend checks | `lib/frontend-contract.ts`, `lib/frontend-routes.ts`, `lib/frontend-usage.ts` |
| `hook-` | Cross-cutting guard shared by every hook | `lib/hook-safety-guard.ts`, `lib/hook-dormancy.ts`, `lib/hook-visibility.ts`, `lib/hook-metrics.ts`, `lib/hook-tool-paths.ts`, `lib/hook-domain-literals.ts` |
| *(none)* | Shared runner | `lib/ast-rules.ts` (scope-agnostic) |

**Payload shapes are read in one place.** `lib/hook-tool-paths.ts` answers "which
files is this call about to write": `write` carries `input.path`, while `edit`
names its files in `[path#TAG]` section headers (and `MV` targets) inside the
patch body. Every write-path guard read only `input.path` and therefore ignored
`edit` entirely — measured by rewriting a **pushed** migration with `edit` and
watching the immutability guard stay silent. The same bypass existed in
`strict-backend-app-structure` and `strict-tooling`. A fourth guard cannot
repeat it: the question has one answer now.

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
| `backend-contract.md` | — | `check-backend-contract.ts` |
| `backend-auth.md` | — | `check-backend-auth.ts` |
| `backend-exceptions.md` | — | `check-backend-exceptions.ts` |
| `backend-api-http.md` | — | `check-backend-api-http.ts` |
| `backend-router-params.md` | — | `check-backend-router-params.ts` |
| `backend-naming.md` | — | `check-backend-naming.ts` |
| `backend-transaction.md` | — | `check-backend-transaction.ts` |
| `backend-migrations.md` | `strict-backend-migrations.ts` — upstream immutability + hand-created revisions blocked toward `make migrate-gen` | `check-backend-migrations.ts` — ORM/DB sync, one-table unpushed revisions, and upstream immutability |
| `backend-table-design.md` | — | `check-backend-table-design.ts` |
| `backend-model-files.md` | — | `check-backend-model-files.ts` |
| `backend-repository-files.md` | — | `check-backend-repository-files.ts` |
| `backend-service-injection.md` | — | `check-backend-service-injection.ts` |
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
| `root-git-workflow.md` | `strict-no-vcs-publish.ts` | — |
| `frontend-makefile.md` | `strict-command-routing.ts` | `check-makefiles.ts` |
| `frontend-code-conventions.md` | `strict-frontend-app-structure.ts` | `check-frontend-code.ts` |
| `frontend-domain.md` | — | `check-frontend-domain.ts` |
| `frontend-api-layer.md` | — | `check-frontend-api-layer.ts` |
| `frontend-screens.md` | — | `check-frontend-screens.ts` |
| `frontend-routing.md` | — | `check-frontend-routing.ts` |
| `frontend-contract.md` | — | `check-frontend-contract.ts` (names, paths, validation parity) + `check-frontend-types.ts` (types, nullability, optionality, verbs, query params) |
| `frontend-i18n.md` | — | `check-frontend-i18n.ts` |
| `frontend-design.md` | — | `check-frontend-design.ts` |
| `frontend-components.md` | — | `check-frontend-components.ts` |
| `code-layout.md` | — | `check-code-layout.ts` |
| `duplicate-blocks.md` | — | `check-duplicate-blocks.ts` |
| `tooling.md` | `strict-tooling.ts` | `check-tooling.ts` + `check-omp-types.ts` (its TypeScript type-checks) |
| `omp-conventions.md` | — | `check-omp-rules.ts` |
| `omp-naming-consistency.md` | — | `check-omp-rules.ts` (rule prefix↔globs) + `check-omp-hooks.ts` (hook name↔paths) |
| `omp-ast-rules.md` | — | `check-ast-rules.ts` (per-rule proof) + `check-omp-hooks.ts` (rule↔hook contract, declared ownership) |
| `omp-hooks.md` | — | `check-omp-hooks.ts` |
| `omp-skills.md` | — | `check-omp-skills.ts` |
| `decks-sync.md` | — | `check-decks-sync.ts` |
| `RULES.md` (sticky) | `strict-no-subagents.ts` | — |
| `RULES.md` (sticky) | `strict-additive-writes.ts` | — |
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

## A Layer Is Deeper Than One Directory

`backend-domain.md` documents the folder shape: a domain that outgrows one file
becomes `models/batch/{schedule,run,step}.py`. **Seventy percent of
the files in `models/`, `schemas/`, `services/` and `repositories/` now live one
level down.** A `readdirSync(dir)` filtered on `.py` skips directories silently,
so a hook written that way keeps reporting PASS while it inspects a third of the
layer it claims to govern.

Audited by planting the same violation twice — once in a flat file, once in a
nested one. Seven scans were reaching too shallow:

| Check | Flat | Nested | What went unchecked |
|---|---|---|---|
| `check-backend-service-injection` | FAIL | **PASS** | 7 of 10 services could import another service |
| `check-backend-table-design` | FAIL | **PASS** | 9 of 13 tables: 1NF, keys, FK `ondelete`/`index`, `String(n)`, CHECK |
| `check-backend-auth` | FAIL | **PASS** | 7 services could raise an undefined exception |
| `check-backend-naming` (conftest imports) | FAIL | **PASS** | 9 tables could vanish from the test database |
| `check-backend-domain` (relationship `lazy=`) | — | **PASS** | **every relationship in the codebase** — all ten are nested, so the check applied to nothing |
| `check-backend-domain` (model AST rules) | — | **PASS** | `id-standard`, `field-mapped-pattern` on 9 tables |
| `check-backend-ownership` (dormancy probe) | — | latent | works only because `services/user.py` happens to be flat |

The `lazy=` row is the shape of the whole class: the check did not weaken, it
stopped applying, and nothing said so. `check-frontend-contract`'s validation
parity had failed the same way one layer up — `schemas/batch.py` had become a
folder, so two of three domains were never compared.

**The rule.** The layout is a value, not a convention: `lib/backend-layout.ts`
declares `APP_LAYERS` — which directories exist under `backend/app/` and how
deep a file may sit in each (`0` flat, `1` folder domains, `null` for `tests/`)
— and three consumers derive from that one declaration:

| Consumer | Derivation |
|---|---|
| `strict-backend-app-structure` (write) | the directory allowlist **and** the depth: `routers/sub/x.py` and `models/batch/sub/x.py` are now refused at write time — both passed the old gate and would then have been visible to no scan |
| `layerFiles()` (read) | the one traversal every layer scan uses |
| `check-omp-hooks` (meta) | the folder-domain layer set (`depth === 1`), so a bare `readdirSync(<layerDir>)` in a backend-scoped hook is rejected |

A scan whose unit is the *domain* rather than the file carries
`// layer-flat-ok: <reason>` within five lines — the reason is required, so an
exemption cannot outlive its argument. A pre-hook edit binds from the next
session; the depth logic is proven by direct execution, not by the gate that
loaded before it existed.

## Unreadable Is a Finding, Never a Pass

A marker-anchored parser that answers "no match" with an empty result retires
its whole check family without a trace — the file exists, compiles, and the
comparisons quietly stop running. Measured twice in one audit:

- reformatting `yup.object({` to `yup\n.object({` (the same program) emptied
  `parseYupRules`, and every length/pattern/required comparison for that dialog
  vanished behind a PASS;
- renaming `SUPPORTED_LANGUAGES` emptied the locale set; the CLI then crashed on
  `LOCALES[0]!` with a nameless stack trace, and at runtime `guarded()` would
  have swallowed that crash and retired the check silently.

The rule has two halves. **Tolerate valid formatting** where cheap (the marker is
now a regex). **Where the parser is still defeated, say so**: a dialog carrying a
`Resolver(` whose schema yields zero rules, or an existing `i18n.ts` yielding
zero locales, is not a clean state — it is input the check cannot read, and the
check's own blindness is the finding. The same shape guards dormancy
(`A Skipped Comparison Is Not a Pass`) and the layer walk above: silence must be
earned by looking, never by failing to look.

## Scope Equals The Claim

A check must fire on exactly what it asserts. The failure is silent in both
directions: a check that reaches further decides something nobody chose (a
member-order scanner that read docstring prose as a field forced a sentence to
be reworded), and a check that reaches less passes while applying to nothing (a
"module-private functions are \`_\`-prefixed" scan anchored at column zero never
looked inside a class, so a method serving one line of its own class sat in the
public surface of every caller).

Both were found by a human, not by a gate. When writing a check, state the
construct it is about and make the pattern say so — track string state when
reading source line by line, and scope by structure rather than by indentation
or line width. `omp-ast-rules.md` carries the same standard for AST rules, with
the four cases measured here.

## Measure The Domain, Never Name It

A hook must discover the domains it governs. Writing a domain's name into a
classifier is the one defect in this harness that fails **silently**: the check
keeps passing, it just stops applying.

Measured, three times in one session, when `models/integration.py` became five
files:

| Hook | What it wrote | What it should have asked |
|---|---|---|
| `check-backend-tests.ts` | `new Set(["integration"])` | does this domain own more than one model file? |
| `check-backend-transaction.ts` | `file !== "integration.py"` | same question |
| `lib/backend-domain-structure.ts` | `name === "integration"` | same question |
| `check-frontend-api-layer.ts` | `/(?:auth\|user\|batch\|integration)/` | which prefixes do the routers serve? |

None of them errored on the day they went blind. The fourth had also been
missing `/health` for its whole life, and nothing said so.

**The rule.** A discoverable domain name may not appear as a literal in a
*classification* position — equality, a membership call (`.has`, `.includes`,
`.startsWith`, `.endsWith`), a collection literal, or a regex alternation.
Discover instead, from the same source the domain checks use:
`services/*.py`, `routers/*.py`, `models/*.py`, or
`frontend/src/lib/api/services/*.service.ts`. Shared helpers already exist —
`aggregateDomains()` / `belongsToAggregateDomain()` in
`lib/backend-domain-structure.ts`, `routerPathSegments()` in
`lib/frontend-routes.ts`.

A literal that *addresses* one file (`join(routersDir, "auth.py")`) is not this
defect: it points at a file the hook is about, and it fails loudly when that
file moves.

**Two escapes, both self-invalidating:**

1. **A dedicated hook may name its domain.** `lib/backend-integration-*.ts`
   exists to check `integration`; measuring that would be circular. Membership
   is read from the hook's own filename, so there is no list to maintain.
2. **`// domain-literal: <reason>`** on the line, or the line above. The reason
   is required and must be a sentence, because some collisions are real —
   `hook-publish-consent.ts` compares a transcript *message role* named `user`,
   which is not the `user` domain. An annotation on a line that classifies
   nothing fails as stale, so exemptions cannot pile up unread.

Enforced by `lib/hook-domain-literals.ts`, run from `check-omp-hooks.ts` over
`post/`, `lib/`, and `pre/`. Rule docs are **not** gated the same way: the same
detector over rule prose was measured at roughly half false positives (the word
"exception" usually means a Python exception), and a noisy gate is worse than a
written standard. So for prose the standard is stated, not enforced — state the
structural property that makes a case special, never the name of the case.


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
| `.omp/ast-grep/rules/frontend-screen/` | `raw-datagrid.yml` | `check-frontend-screens.ts` (scans frontend/src, excluding `ServerDataGrid.tsx`) |
| `.omp/ast-grep/rules/frontend-api/` | `inline-axios.yml` | `check-frontend-api-layer.ts` (scans frontend/src, excluding `lib/api/client.ts`) |

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
| +-- strict-additive-writes.ts # Cross-cutting: blocks an edit only when a registration/import entry would survive nowhere in the file (dedupe and same-patch moves pass; tests/ is exempt — a lost import there fails loudly at collection)
| +-- strict-no-vcs-publish.ts      # Cross-cutting: denies git commit/push — VCS belongs to the user (RULES.md)
| +-- strict-backend-app-structure.ts # Backend: blocks writes outside the documented backend/ structure (new dirs under app/, stray app-root files, non-standard backend/ dirs)
| +-- strict-frontend-app-structure.ts # Frontend: blocks writes outside the declared frontend/src/ layout (SRC_LAYOUT — new top-level dirs, stray src-root files)
| +-- strict-tooling.ts            # Cross-cutting: blocks writes of Python/shell tooling and root script dirs outside .omp/hooks/ (write only — an existing file is fixed forward)
+-- post/
  +-- check-backend-domain.ts      # Read-only: validates 5-layer CRUD domain pattern
  +-- check-backend-contract.ts    # Read-only: validates backend surface is reachable from an entry point
  +-- check-backend-migrations.ts  # Read-only: validates ORM ↔ DB sync and migration scope
  +-- check-backend-table-design.ts # Read-only: validates table design invariants (1NF, keys, constraints)
  +-- check-backend-model-files.ts # Read-only: validates one table / one class / one file
  +-- check-backend-repository-files.ts # Read-only: validates one repository / one table / named after it
  +-- check-backend-service-injection.ts # Read-only: validates a service imports no other service
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
  +-- check-frontend-domain.ts     # Read-only: validates the frontend 6-layer domain pattern
  +-- check-frontend-api-layer.ts  # Read-only: validates one client, query keys, cache policy, invalidation
  +-- check-frontend-screens.ts    # Read-only: validates the per-screen-type templates
  +-- check-frontend-routing.ts    # Read-only: validates paths ↔ routes ↔ navigation and the layout guards
  +-- check-frontend-design.ts     # Read-only: validates the design system (tokens, metrics, vocabulary)
  +-- check-frontend-components.ts # Read-only: validates component boundaries (no shape written twice)
  +-- check-frontend-contract.ts   # Read-only: validates frontend types/endpoints against the backend
  +-- check-frontend-types.ts     # Read-only: validates request/response types, nullability, verbs, query params
  +-- check-frontend-i18n.ts       # Read-only: validates locale parity, referenced keys, hardcoded text
  +-- check-duplicate-blocks.ts   # Read-only: duplicated block runs in the file just written (delete, don't renumber)
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

### The Measured Failure Classes — walk these before writing

Every class below retired a real check in this repository while the gate stayed
green. A new hook (or a change to an old one) answers each question **at
authoring time**; the mechanical guard catches the answer you forgot to give.

| Class | The question | Mechanical guard |
|---|---|---|
| **Shallow layer walk** — a flat scan of a layer that holds folder domains | does my scan descend where the layout allows depth? | `checkLayerTraversal` rejects bare `readdirSync(<layerDir>)`; traverse via `layerFiles()`; domain-unit scans say `// layer-flat-ok: <reason>` |
| **Vanished prerequisite** — `readIfPresent → null → return`, check family retires silently | who owns this file's existence — tsc, another check, a downstream sentinel? | `checkSilentPrerequisites` demands `// existence-ok: <reason>` or a reported absence |
| **Defeated parser** — the file exists and compiles, the marker regex misses, comparisons run on empty sets | what does my check report when it parses *nothing* from a file that exists? | no general guard — write the sentinel by hand (`rules.size === 0`, `LOCALES.length === 0`, `registry.size === 0` are the three shipped) |
| **Vacuous both-ways** — two parsed sets compared, both empty, trivially equal | can both sides of my comparison empty at once, and would I notice? | same sentinel discipline; a comparison earns silence by having compared something |
| **Named domain** — a discoverable name written into a classifier | am I naming what I should be measuring? | `hook-domain-literals`; discover from the layout/services, never list |
| **Skipped-is-passed** — a precondition gate that prints the same PASS either way | does my banner distinguish "checked and clean" from "nothing to check"? | dormancy contract (`dormant()` banner); `A Skipped Comparison Is Not a Pass` |
| **Silent crash** — a throw in a handler retires the hook for the session | is my body inside `guarded()`? | `checkCrashGuard`, TTSR `omp-hook-crash-guard` |

The common shape: **silence must be earned by looking.** A check may be quiet
because it looked and found nothing — never because a rename, a folder move, a
reformat or a missing file kept it from looking. When one of these fires during
authoring, the annotation it demands *is* the consideration: it forces the
classification onto whoever writes the site, not onto the next audit.

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

### Reading the edited path (`path-raw-ok`)

An anchored edit does not hand the hook a clean path: it carries a content tag,
`backend/app/main.py#0D77`. A guard that matches that string against an
allowlist, an extension test or a directory prefix is matching a path that
exists nowhere — so it either refuses a legitimate edit or waves it through in
silence, and both failures are invisible from the outside. Strip the tag where
the path is read:

```ts
const path = String(event.input.path ?? "").replace(/#[0-9A-Fa-f]{4}$/, "");
```

The field can also be absent. A patch-form edit arrives as
`{ input: "[relative/path#TAG]\nPUT 12.:\n+..." }` with no `path` at all, and a
guard that only reads `path` then sees nothing to judge. When the target matters,
read the patch header as a fallback — and when neither is there, fail open (a
pre hook that throws costs the agent the whole tool call).

`check-omp-hooks` requires every `input.path` read under `pre/` to strip the tag
on the spot, or to carry `// path-raw-ok: <reason>` within the five lines above
it.

### Every execution channel (`channel-ok`)

Commands do not only arrive through `bash`. The `eval` tool carries a Python or
JS body in `input.code`, and that body reaches the same binaries through
`subprocess.run([...])`, `os.system(...)` or `execSync(...)`. A guard that reads
`input.command` and filters on `bash` alone therefore states a policy that the
very next tool call can step around without breaking a single rule.

A guard that inspects a command string accepts `eval` as well, reads
`input.code` next to `input.command`, and gives the same guidance on both
channels. If the policy really is shell-shaped, say so with
`// channel-ok: <reason>`.

### The context parameter is not readable (`ctx-ok`)

A `tool_call` handler's second argument is the extension context. An exception
thrown inside a pre hook is promoted to a **tool failure**: the tool call dies
and the agent receives the crash instead of its result. Every read of that
parameter is a candidate — a property that is undefined in some call shapes, a
getter that throws — so the decision to block is made from `event` alone and the
parameter is written `_ctx: unknown`. If a hook genuinely needs it, it says why
with `// ctx-ok: <reason>`.

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
|`check-backend-domain.ts`|5-layer CRUD pattern across `backend/app/`|Model files ↔ schemas/repositories/services/routers pairs; model `Base`/`AuditMixin`/`id`/`name`/`description`; 6 Pydantic classes + per-class `extra="forbid"` + Read `from_attributes` + Read `version: int`; the schema layer exports classes only (no public function but `to_read`/`to_read_list` — measured: a record mapper and a timestamp normaliser parked in `schemas/` because a sync `def` is banned in `services/`); a `*CreateRequest`/`*UpdateRequest` string field declares `max_length` and never above its column's `String(n)` — over it, or absent, the database refuses the value as a 500 instead of the schema refusing it as a 422 (requests only: a read response carries what the row holds); a column carrying `CheckConstraint("<col> IN (...)")` is exposed as a `Literal` of exactly those values in the schema file that mirrors its model file — the constraint decides the vocabulary and the schema is where it is kept, so a `str` there throws the set away at the only layer a client reads (measured: `integration_field` kept four vocabularies through all three layers while `batch_run.status`/`trigger`, `batch_step.status` and `integration_call.method`/`outcome` were `str`, and the TS unions had been narrowed by hand answering to nothing); service never assigns `updated_at`; 6 repository methods (`find_stale` is banned by name — measured: fourteen definitions, zero business callers, and a blanket `created_at` purge deletes active rows; retention finders are per-domain: `find_expired`/`expires_at`, `find_finished_before`/`finished_at`); service `session.begin()` + `NotFoundError`; 5 REST endpoints; `Annotated[T, Depends(factory)]` DI; router in `main.py`; model in `alembic/env.py`|
|`check-backend-table-design.ts`|Table design invariants in `backend/app/models/` (mapped classes **and** column-bearing mixins)|`__tablename__` present/snake/singular; primary key; `AuditMixin` inherited plus its own columns + `version_id_col`; atomicity — no numbered repeating groups (1NF); Booleans NOT NULL; `DateTime(timezone=True)`; foreign keys `_id` + `ondelete=` + `index=True`; explicit `String(n)` lengths; short type/status/mode strings carry an `IN (...)` check constraint|
|`check-backend-model-files.ts`|Model files in `backend/app/models/`|One `__tablename__` per file, the file named after its table, one mapped class per file — measured: four tables in one file forced a filename exception into three separate readers|
|`check-backend-repository-files.ts`|Repository files in `backend/app/repositories/`|A file's own `select(Model)` targets only the table its name declares; child-table column projections and aggregate-root child construction are exempt|
|`check-backend-service-injection.ts`|Service files in `backend/app/services/`|No `from app.services` import — a service composes repositories, never another service|
|`check-backend-exceptions.ts`|Core exception policy across `backend/app/`|`ast-grep/rules/exceptions/` (no builtin raise outside a Pydantic validator, no `HTTPException` raised **or constructed**, no `raise stored_instance`); every raised class defined in `app/core/exceptions.py`; class ↔ `@app.exception_handler` both ways with a parent-handler allowance for subclasses; one handler per class; uniform body (`detail`, `code`, `request_id`) with an explicit `status_code`; every code a snake_case identifier (it is the locale key `errors.<code>`, not prose); **a class carrying only `detail` is not raised for two different reasons** — the difference would live solely in the string no screen may render, so the causes reach the user as one sentence (measured: `ConflictError` had 8 raise sites all answering `conflict`, and a form had guessed `conflict: 'name'` for failures about no field at all; exempt by construction — no `detail`, an existing `code` parameter, structured fields beyond `detail`, or a single raise site); `*Error` naming; third-party mappings (`StaleDataError`) declared in the allowlist|
|`check-backend-api-http.ts`|`api/*.http` structure, runnable sequencing, endpoint + external API coverage|File ↔ router both ways and location (`api/`, not `backend/api/`); structure (`### <Name> API` title, `### 전제:`, `@base`, named login block before the first token use, sections numbered 1..n with the status declared after a dash); Bearer on non-public requests (a `— 401` block omits it on purpose); one request block per `@router.<method>`; no literal UUID in a request line; CRUD sequencing (create → list → get → update → [409] → delete → [404]) with the id chained from the named create block and a dynamic create body when the model declares uniqueness; **state neutrality** — balanced `— 201` creates vs `— 200` deletes per collection, the actor contract — `auth.http` alone creates/deletes the account it logs in as, every domain file logs in as the seeded actor (`@actorUsername`/`@actorPassword`, `make db-init` named in `### 전제:`; the row comes from `57_seed_api_actor_user.py`), and seeded rows never deleted; a success-path (`— 200`) execute block per seeded integration operation; **runtime proof** — `lib/backend-api-flow.ts` and the `check-api-flow` target must exist and be wired to each other|
|`check-backend-router-params.ts`|Router parameter standard in `backend/app/routers/`|Four parameter kinds (path / `*Request` body named `data` / `*Dep` dependency / `*Query` alias) and nothing else; route template ↔ signature both ways; `*_id` path params typed `UUID` with no default; one body on writes only, none on GET/DELETE (form dependency is the documented exception); root `GET /` list reads paginated through `OffsetQuery`/`LimitQuery` (parent-scoped sub-collections exempt but must be path-scoped); `LimitQuery` declares `ge=`+`le=` and `ITEMS_PER_USER` ≤ the cap; signature order path → body → dependencies → query; routers declare no local `Annotated` alias|
|`check-backend-auth.ts`|Auth + domain exception patterns|`router/` AST rules (all endpoints authenticated, write-auth, inline `Depends`, response model), `service/` AST rules (no `HTTPException` in services), `conventions/` current-user-router-only, exception handler registration|
|`check-backend-naming.ts`|Naming + encapsulation in `backend/app/`|File/variable naming AST rules; module-private functions prefixed `_`, class-private methods prefixed `_` in the five encapsulated layers (the module check is anchored at column zero and never looked inside a class), and a `_` name never imported by another module (otherwise the prefix is a rename away from meaningless); repository access forbidden outside its owning service|
|`check-backend-transaction.ts`|`session.begin()` placement|`transaction/service-only.yml` — bare, `self.`, and aliased (`svc.session.begin()`) forms forbidden outside services (incl. `app/batch/`); `domain/` write-only transaction rules|
|`check-backend-migrations.ts`|ORM ↔ DB sync and migration scope|`alembic check` autogenerate diff (ORM drift and DB drift); skipped silently when the database is unreachable|
|`check-backend-batch.ts`|Batch job conventions in `backend/app/batch/`|module named after its single public job (`app/batch/<job_code>.py`) and `BATCH_JOBS` keyed by that same name; `engine` used directly; `Service(session)` constructor; `service.repository` access (never raw session); meaningful count/status return; `async def`; the schedule chain (registry → seeded `batch`/`batch_schedule` row → scheduler options); the lifespan loads the schedule **and sweeps orphaned runs** (`update_interrupted_runs` — main.py is outside coverage, so a deleted sweep call fails nowhere else); the run contract (a job that walks a provider records a step, and a step is recorded only under `current_run_id`); the provider-job shape of `sync_<provider>_ledgers.py` (the four facts `PROVIDER_CODE`/`PAGE_SIZE`/`END_CODES`/`SYNCED_BY`, a nonempty `FEEDS` whose every `Feed` names a seeded operation of that provider and the `replace_<table>_ledger` of a known ledger service — read by `lib/backend-ledger-feeds.ts` — every walk passing `page_size=PAGE_SIZE`/`end_codes=END_CODES`, one paging family per job, `LedgerFloorError` caught, the retired names `MAX_PAGE_SIZE`/`DEFAULT_MAX_*`/`total_count`/`find_checkpoint` absent outside docstrings); each feed's `from_record` reads every seeded response key or lists it in `UNSTORED_KEYS`; both ways between seeds and jobs — a `Feed` names an operation of the job's own provider (operation → provider read off the seed's `PROVIDER_ID`, renames followed), and every configured operation that pages (`range_start`/`page_no` among caller inputs) is a `Feed` of some `sync_*_ledgers.py`, the message naming the job it belongs in|
|`check-backend-tests.ts`|Backend test standard in `backend/tests/`|Every CRUD model has `test_<name>.py`; each covers 10 standard API cases and asserts status 201/401/404/422; auth standard in `test_auth.py`; conftest swaps `async_session_factory` (real `get_session()`, no override)|
|`check-backend-app-setup.ts`|App setup in `main.py`|`GET /health` (DB ping, 503); `FastAPI(title=...)`; routers under `/api/v1`|
|`check-backend-core-config.ts`|Core config in `app/core/`|`@field_validator` decorator in settings; `pool_size`/`max_overflow`/`pool_timeout` in `core/database.py`; `code`/`request_id` in error schema|
|`check-backend-rate-limit.ts`|Rate limiting in routers|`@limiter.limit` on login/signup; 429 + Retry-After when limiter used|
|`check-backend-middleware.ts`|Middleware stack in `main.py`|CORSMiddleware with `allow_origins`; `CsrfProtection` validating Origin + Sec-Fetch-Site; each security header as its own claim; `X-Request-ID`; `core/logging.py` exists; **registration, not just definition** — `TrustedHostMiddleware`, `CsrfProtection`, `SecurityHeaders` and `CORSMiddleware` must each appear in an `add_middleware(...)` call, because deleting the registration left every header string inside the class body and the check stayed green|
|`check-backend-background-tasks.ts`|Background tasks in routers|No raw `asyncio.create_task`; `background_tasks.add_task` when BackgroundTasks used|
|`check-backend-ownership.ts`|Ownership in services|`created_by == current_user` placed in the service that loads the row, never in a router — the check reads placement, not which exception is raised
|`check-backend-audit-log.ts`|Audit endpoint|`GET /audit` with created_by/updated_by; never hashed_password|
|`check-backend-redis-cache.ts`|Redis cache|Subject-scoped keys; per endpoint: `GET` sets `ttl_seconds=`, writes call `cache.invalidate()`|
|`check-backend-file-upload.ts`|File upload|`UploadFile` with max_size + content-type allowlist|
|`check-backend-sse.ts`|SSE endpoints|`EventSourceResponse` + `AsyncIterable[ServerSentEvent]` — not raw StreamingResponse|
|`check-backend-api-keys.ts`|API key auth|`X-API-Key` dependency + ServiceAccount model|
|`check-backend-integration.ts`|External API integration|`IntegrationClient` base + `httpx2.AsyncClient` + timeouts + retries + integration exceptions; `httpx2` confined to the client and its wiring|
|`check-backend-integration-configuration.ts`|Database-managed outbound integration configuration|Four tables (provider, named `integration_secret`, operation, unified `integration_field`), DB resolution, request JSON Schema, request sources, secrets resolved through the field's `secret_id` FK and never echoed, mapping as the only response contract (`response_root` absent → one record, at a page → every element; no `response_mode` column) with a page-mapping loop in the client, no `response_schema`/sparse value columns, external API contract tests (`test_integration_external_api.py`), spec fidelity (every seeded field carries `description`), and JSON/XML `response_format` decoding|
|`check-environment.ts`|Env contract (root docker-compose + backend)|Required vars (`ENV`, `DATABASE_URL`, `ADMIN_EMAIL`, `ITEMS_PER_USER`, `APP_NAME`) in `backend/.env`/`.env.example`; matching `settings.py` fields; `.env` ↔ `.env.example` key + section + per-variable comment pair sync (root + backend, bidirectional); root ↔ backend shared var value sync + common-key comment parity + root⊇backend key invariant (backend-only key → container silently uses default); **compose wiring** — the backend maps root `.env` through `env_file` and declares no `environment:` block (a per-key list dropped `SECRET_KEY` and crash-looped the container), every other service's values are `${VAR}` references root `.env` defines, container-local bindings (`0.0.0.0`) excepted; shared var order + comments; AST rules (no `os.environ`/`os.getenv`, no hardcoded connection strings/ports)|
|`check-backend-contract.ts`|Reachability of `backend/app/` surface from an entry point|A `*ServiceDep` alias injected by no endpoint (an `Annotated[X, Depends(...)]` has exactly one consumer, so one without a router is dead by construction — measured: `food_barcode` and `batch_checkpoint` each carried one, mandated by `backend-domain`); a public service/repository method beyond the CRUD template with no caller in `app/` (tests are not callers — a method covered only by its own test is what this check exists to find); properties matched as `.name`, never `.name(`|
|`check-frontend-code.ts`|Frontend code conventions in `frontend/src/` (recursive)|Entry files (`main.tsx`, `App.tsx`, `styles.css`); no class components and no `React.FC`; `@/` alias (no relative import); no hardcoded port; file named after its default-exported component; every imported package declared in `frontend/package.json`|
|`check-frontend-domain.ts`|Frontend 6-layer domain pattern in `frontend/src/`|Domains discovered from `lib/api/services/*.service.ts` (`auth` exempt as a session, not a resource); per domain — `types/<domain>.ts`, `<DOMAIN>_ENDPOINTS`, `<domain>Keys`, five service functions, five query hooks, `<Domain>List.tsx` + `<Domain>FormDialog.tsx`, `<Domain>Page.tsx`; a section directory with no service is an orphan|
|`check-frontend-api-layer.ts`|Transport + cache contract in `frontend/src/lib/api/`|`ast-grep/rules/frontend-api/` (no second `axios.create`); `fetch` and the axios import confined to `lib/api/client.ts`; no backend path literal outside `endpoints.ts` (route registry and the client's 401 list exempt); a service never caches and always imports the shared client; per query hook — key from the factory, `staleTime` from `QUERY_STALE_TIME`, `placeholderData` on every `use*List`; every `useCreate/useUpdate/useDelete` invalidates; a scope **no mutation invalidates** is cached `REALTIME` — `invalidateQueries` is the only refresh path, so a window nothing can end shows last night's run as still going (one-way: an invalidated scope may still pick REALTIME), and every scope the factory declares is read by some query (`authKeys` was exported and referenced by nothing); scopes discovered from `queryKeys.ts`, never listed; sections and pages never import a service|
|`check-frontend-screens.ts`|Per-screen-type templates in `frontend/src/sections/`|`ast-grep/rules/frontend-screen/` (no raw `DataGrid`); list screens carry `useDataGridState` + `ServerDataGrid` + `useCrudDialog`, an `isError` branch and an `emptyTitle`; `rowActionsColumn` declares `count` equal to its **widest** action branch — the number sizes the column, so a low one clips buttons nobody can then click and a high one takes width off the data columns (a maximum, not an equality: the edit-in-place screen's save/cancel branch is shorter than its own default branch, and an equality form fired on it); form dialogs use `useForm` + a resolver + `FormProvider` + `methods.reset` and hold no field state in `useState`; a `detail/` tab imports no query hook; any `mutateAsync` is paired with `toast.error`; pages routed under `DashboardLayout` render `PageHeader` and fetch nothing|
|`check-frontend-routing.ts`|Routing contract in `frontend/src/`|`PATHS` ↔ `App.tsx` ↔ `NAV_ITEMS`, all pairs both ways (`root` and `auth.login` are the documented non-navigation leaves); no literal `to=`/`navigate()`/`path=` outside the registry; `AuthGuard` in `DashboardLayout` and `GuestGuard` in `AuthLayout`, and no guard inside a page|
|`check-frontend-design.ts`|Design system in `frontend/src/`|Ported design modules present and applied by the theme (`palette`, `typography`, `shadows`, `customShadows`, `componentOverrides`); no colour literal outside `theme/palette.ts`; no spelled `boxShadow` (`'none'` excepted) or `fontSize`/`fontWeight` literal outside `theme/`; no raw icon id at an `icon=` prop (the registry `components/iconify/icons.ts` owns ids and asset paths); no layout metric (nav width, header height/mobile) retyped outside `config.ts`; `Chip` never used as a status badge (`Label` is); a `*DetailDialog` body is `background.neutral` and every `detail/*Tab` renders a `DetailSection`; `styles.css` stays a reset — it once clamped the document to 40rem and squeezed the shell into a strip|
|`check-frontend-components.ts`|Component boundaries in `frontend/src/`|No sibling section repeats another's tag sequence, no two exports are the same component, no `*Edit*`/`*Create*` twin file — measured: the run panel drew the failure result beside the success result|
|`check-frontend-contract.ts`|Backend ↔ frontend contract|`<Domain>ReadResponse` fields ↔ `interface <Domain>` (inherited fields resolved, both directions); `AuditMixin` + id ↔ `AuditedResource`; the uniform error body (`detail`, `code`, `request_id`) ↔ `ApiErrorBody`; **route coverage** — every `@router.<verb>` in *any* router module ↔ the (verb, path) a service call **a screen can reach** (service fn → query hook → screen; `auth` is consumed by `JwtContext` by design), both ways, paths normalised to `{}`: a route with no caller is a screen missing or an endpoint that should not be published (declare it in `NOT_FROM_BROWSER` with its reason, and an exemption whose route disappears fails too), a call no router serves is a 404 the user finds, an `<X>_ENDPOINTS` entry no service uses is dead, a service function no hook calls is dead, and a hook no screen renders is a feature never built — measured: secrets create/delete had no caller and `DELETE_SECRET` was declared and never called; **validation parity** — lengths from `Field(min_length/max_length)` on `<Domain>CreateRequest` (module constants and inheritance resolved) ↔ the `yup` chain in `<Domain>FormDialog`, and *shape* rules both ways: a form pattern (`.matches`/`.email`/`.url`) requires a server one — Pydantic `pattern=` **or** a service rule (`*_PATTERN.fullmatch(field)`, `urlsplit(field)`) — a server shape rule requires a form one, and **required runs both ways** (no server default ⇒ `.required()`; a server default ⇒ not required; booleans exempt, a checkbox always submits). a dialog whose resolver yields zero parseable yup rules is reported instead of silently compared against nothing. A **folder domain** reads as the concatenation of its modules — `schemas/batch.py` had become `schemas/batch/*.py`, so the lookup returned null and two of the three domains were never compared while the check reported PASS. Measured: a client-only rule let `curl` store `not-an-email` with a one-character password (201); an invented `code` pattern blocked the app's own seeded provider; and reading only Pydantic left the form with no pattern while the service refused `BAD Code` with a 422. **Panels are forms too** — the dialogs hold only strings, so every numeric bound lives on a nested record: a `<Name>Panel.tsx` control declares the bound its `<Name>CreateRequest` field declares (`ScalarField` → `maxLength`, `NumberField` → `min`/`max`), and only the bounds the control can violate (`NumberField` strips non-digits, so `ge=0` is already guaranteed and `gt=0` is not — `0` is what an emptied input returns). Measured: two capped strings and two `gt=0` timeouts declared nothing|
|`check-frontend-types.ts`|Typed backend ↔ frontend contract|Only models that **cross the wire**: roots are the bodies the routers accept (`data: <X>Request`) and the models they return (`-> Page[X]` unwrapped), closed transitively through field annotations so a nested `IntegrationOperationCreateRequest` stays in — a schema set the domain rule requires but no endpoint takes or sends (`batch_run`, `batch_step`) has no client shape to declare. Request bodies (`<Domain>CreateRequest`/`UpdateRequest` ↔ the TS interface of the same name: required fields present, optional ones may be omitted, no extra client field); **types** — every annotation maps to one TS type (`str`/`UUID`/`datetime` → `string`, `int`/`float` → `number`, `bool` → `boolean`, `list[X]` → `X[]`, `dict`/`JsonObject` → `Record<string, unknown>`, `object` → `unknown`, `Literal[...]` → the same union, `<X>ReadResponse` → `X`), inheritance resolved across `types/api.ts`; **nullability** — `X \| None` in a response is `T \| null`; **optionality** — a request field with a default is `field?:` (a bare `= Field(...)` is not a default); **verbs** — the method a service calls is a method the route declares (endpoint keys read per `<DOMAIN>_ENDPOINTS` block, because `LIST`/`DETAIL` repeat and a flat map hid a wrong verb); **query params** — every `Annotated[int, Query(...)]` parameter exists in a params type; **request guarantees** — the generic a service passes matches the handler return annotation (`list[X]` -> `X[]`, `dict[str, bool]` -> `OkResponse`), a `Form(...)`/`OAuth2PasswordRequestForm` handler is called form-encoded and no other one is, an endpoint constant takes exactly as many arguments as its route has path parameters, and every page size the UI offers is inside `Query(ge=, le=)`. An annotation the parser cannot read is reported, never assumed equal|
|`check-frontend-i18n.ts`|Translation contract in `frontend/src/locales/` and its call sites|`ko` ↔ `en` key parity both ways (a `.d.ts` is not a locale — `i18next.d.ts` declares the *types* of the files beside it, and reading it as a language would demand a locale named `i18next`); every literal `t('key')` resolved through the namespace its alias was bound to (`useTranslation('ns')`, default `common`); no Hangul outside `locales/`; **error-code parity** — every code the backend can emit (handler literals, `code=` at a raise site, `<THING>_CODE` module constants) has `errors.<code>` in every locale and no `errors.*` key is dead, with `errors.unknown` always present for a failure that never reached a handler; **no server string on screen** — `apiError.message` / `toApiError(error).message` / `.detail` never reach a toast or JSX (`lib/`, `components/hook-form/` and `formState` reads exempt). an existing `i18n.ts` that yields no locales is reported, never looped over as an empty set. Key *existence* is the compiler's job, not this hook's: `locales/i18next.d.ts` types the resources, so a missing or composed-from-`string` key fails `tsc`|
|`check-duplicate-blocks.ts`|Duplicated block runs in source files just written (backend, frontend `src/`, `api/*.http`, `decks/scripts`; data formats exempt)|A non-overlapping repeat of 24+ identical consecutive lines is a duplicated block — report it at write time and instruct deletion, not renumbering (2026-09-01 renumbering-loop incident)|
|`check-code-layout.ts`|Code layout across **every** code surface (backend Python incl. `scripts/`, frontend `src/` + package-root config, `decks/scripts/*.mjs`, `.omp/hooks/`)|Comments (no commented-out code, no parked-work markers, JSDoc header on every hook/lib); section banners in `backend/app` + `backend/scripts` (vocabulary, order, `Imports` first — empty `__init__.py` exempt); module constants under the `Constants` banner above the first class, and `const` never `let` in TS/JS; Python class member order (declarative config → fields → relationships → properties → `__init__` → public → private, dunders exempt); TS/JS class member order (fields → constructor → public → private); file layout (imports, constants, `export default`, then helpers)|
|`check-makefiles.ts`|Makefile target consistency (backend, frontend, root, check-verify)|`.PHONY` targets implemented; `##` documented targets in `.PHONY`; documented targets exist in Makefile; actual targets documented — compared against rule markdown tables; **verify membership** — every post-hook-backed `check-*` target is a prerequisite of `verify`, and the prerequisite list equals the `make verify` row in `root-makefile.md` (both directions)|
|`check-decks-sync.ts`|Decks ↔ harness sync (decks/harness-rules/slides.md)|Every rule file, pre/post hook, and AST rule dir is mentioned in the deck source (additive check — missing artifacts flagged)|
|`check-tooling.ts`|Tooling language policy across the tree|Python confined to `backend/app`, `backend/tests`, `backend/alembic`; the only shell script is `backend/scripts/start.sh`; `.omp/hooks/` is TypeScript only; no root `scripts/`/`tools/`/`bin/`/`utils/` directory; scripts only under `.omp/hooks/`, `frontend/`, `decks/`; every root `check-*` target runs `node .omp/hooks/...`|
|`check-omp-types.ts`|Harness TypeScript type-checks|`tsc --noEmit` over `.omp/tsconfig.json` (62 files); reports the first 3 `error TS` lines|
|`check-omp-hooks.ts`|`.omp/hooks/` ↔ `omp-hooks.md` directory-structure sync + hook functional contract + rule↔hook mapping|Every hook listed in `omp-hooks.md` exists on disk (dangling ref); every actual `.omp/hooks/**/*.ts` file is listed in `omp-hooks.md` (orphan); the file-name prefix (`post/check-*`, `pre/strict-*`) that every contract check is keyed by; post hooks must call `buildSafeWarning` + `wrapWarning` and must not implement `lastWarning`; the guard call shape — `buildSafeWarning(event.toolName, "<hook>", issues, fixHint)` with the hook's own name used in `buildSafeWarning`/`wrapWarning`/`resetSuppression` (a dropped argument used to kill the hook with `visible.map is not a function`); the crash-guard contract — `guarded` imported from `lib/hook-visibility.ts`, one wrapper counted per `pi.on("tool_result")` registration, and the name it declares equal to the file's; `lib/hook-visibility.ts` itself logs the crash, appends to the original content, and never rethrows; `MUTATING_TOOLS` filter required; pre hooks `return { block: true }` (deny execution); every rule maps to ≥1 hook and every hook to ≥1 rule plus the authoring meta-checks: layer traversal (`layerFiles()` or `// layer-flat-ok:`), silent prerequisites (`// existence-ok:` or a reported absence)|
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
(`RULE_NAME_EXCEPTIONS` for non-1:1 names, existence-verified); a check whose
name resolves to no rule prints nothing rather than misattributing. The sandbox
tree enforces this statically in `check-omp-hooks` (`printRuleHint` required on
every CLI tail, rule-less checks listed in `NO_RULE_CHECKS` with a reason); this
tree adopts the hint check-by-check, and the static enforcement lands with full
adoption.

### Warning Shape

An issue line names **where**, **what**, and **how**: `main.py: CORS missing —
add CORSMiddleware (dev origin http://localhost:25173)`. The line number belongs
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
   `// hook-scope: global — <reason>` comment. Measured 2026-08-29 (sandbox):
   one mutating tool result cost 6.8s across the 36 post hooks (write) and 4.9s
   (bash), and 3.3s of that was harness meta checks firing on a `backend/` edit.

### Demand direction (요구는 의존 방향으로)

검사는 **존재하는 하류가 상류를 요구**한다. 작업의 첫 걸음에서 마지막 걸음을 요구하지 않는다.
왜 중요한가: 이 지적들은 매 변이 도구 결과에 주입된다. `app/models/x.py` 하나를 만들면 schema·repository·
service 누락과 라우터 미등록·DI 미배선까지 다섯 건이 한 번에 나가고, 작성자는 그 목록을 작업 큐로 읽는다.
한 계층만 손보려던 작업이 도메인 전체로 번지는 경로가 이것이다.

파일이나 등록의 **부재**를 지적하는 문장은 둘 중 하나여야 한다 — `check-omp-hooks` 가 강제한다:

- **앵커 명시**: 무엇 때문에 요구가 생겼는지 메시지가 밝힌다(`routers/x.py exists but service file is missing`).
- **`// premature-ok: <사유>`**: 어느 단계에서든 참인 요구다. 예: 프로젝트 기반 파일의 부재(설정 결함이지
  작업 순서가 아니다), `alembic/env.py` 등록(autogenerate 는 import 없는 모델을 보지 못하므로 모델 자체의 속성).

내용 검사(클래스·메서드·필드 부재)는 대상이 아니다 — 이미 존재하는 파일의 속성이기 때문이다.

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

## Break It Once, Before You Trust It

A check that passes proves nothing about a dirty tree; it may be asleep. Three
times in one session a check reported PASS on a violation it claimed to own — a
digit-only literal parser, TypeScript inheritance resolved per file, and
`useUser` matched as a prefix of `useUserList`. Every one was found by breaking
the tree on purpose while writing the check.

So the rule is a working practice, not a machine:

**When you add or change a claim, violate it once and paste the failure into the
commit message.** Copy the tree (or edit and revert), plant the smallest
violation, run the owning check, and read *which* message fired.

Reading the message matters more than the exit code. A falsification of the
path-arity claim once changed the path as well: route coverage failed instead,
the arity claim never ran, and the author read the output as a pass.

### Why this is not automated

A standing mutation suite was built and removed. Measured, over 38 cases:

- the three real parser defects above were found while writing the checks, never
  by the suite
- the suite’s own finds were mostly its own bugs (matching a banner line instead
  of a `FAIL:` line; a scratch copy without `.git`, which turned 19 migration
  claims into phantom failures)
- 16 cases anchored in product internals: six never fired at all, and the rest
  would break on a rename the product is free to make
- a per-check coverage gate turned “prove the claims” into “produce 40 cases” and
  found no defects

What did find defects, both times, was an ad-hoc probe written for one question:
planting a limiter and a raw `StreamingResponse` showed that
`check-backend-rate-limit` only looked at two files and that
`check-backend-sse` collected its AST violations and then dropped them in a
dormancy early-return. Both are fixed. Neither needed a suite.

Dormancy stays visible the cheap way: `make hook-report` lists which hooks have
never warned across measured runs.
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
- `make check-backend-contract` → `node .omp/hooks/post/check-backend-contract.ts`
- `make check-backend-table-design` → `node .omp/hooks/post/check-backend-table-design.ts`
- `make check-backend-model-files` → `node .omp/hooks/post/check-backend-model-files.ts`
- `make check-backend-repository-files` → `node .omp/hooks/post/check-backend-repository-files.ts`
- `make check-backend-service-injection` → `node .omp/hooks/post/check-backend-service-injection.ts`
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
- `make check-frontend-domain` → `node .omp/hooks/post/check-frontend-domain.ts`
- `make check-frontend-api-layer` → `node .omp/hooks/post/check-frontend-api-layer.ts`
- `make check-frontend-screens` → `node .omp/hooks/post/check-frontend-screens.ts`
- `make check-frontend-routing` → `node .omp/hooks/post/check-frontend-routing.ts`
- `make check-frontend-design` → `node .omp/hooks/post/check-frontend-design.ts`
- `make check-frontend-components` → `node .omp/hooks/post/check-frontend-components.ts`
- `make check-frontend-contract` → `node .omp/hooks/post/check-frontend-contract.ts`
- `make check-frontend-types` → `node .omp/hooks/post/check-frontend-types.ts`
- Falsification has no runner target: each check is falsified where it is written, by
  planting the violation, watching it fire, and restoring — the evidence lives in the
  check's own comment (`lib/frontend-record-dialog.ts` names the eight it caught)
- `make check-frontend-i18n` → `node .omp/hooks/post/check-frontend-i18n.ts`
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
| Every post hook declares a path scope (`touchesPath`/`touchesStrict`) or a `// hook-scope: global — <reason>` | a check that runs on events outside its domain spends the agent's wall clock, not just context | one write cost 6.8s of hook time; the meta checks in it (2.7s `check-omp-hooks`, 0.4s `check-omp-types`) had nothing to do with the edited file (2026-08-29, sandbox) |
| Only `post/check-verify.ts` may execute the project gate (`make`, `pytest`, `ruff`, `pyright`, `npm`, `uv`) | the gate is 54% of all hook time (1,120s of 2,058s) and a second runner races the agent's own `make` | one owner today |

records the kinds its own cases produce and fails on any declared kind that never
fired. A threshold nobody can drive is a threshold nobody can change safely.

## Never Do These

- Run the project gate (`make verify`, `make test`, `pytest`, `ruff`, `pyright`,
  `npm run build`) from any post hook except `check-verify` — read files instead
- Put blocking logic in post hooks — they can't block tool calls
- Mix pre and post hooks in the same directory
- Reference `make verify-rules` or `scripts/verify_rules.ts` — they do not exist; use `make verify`
- Forget to keep `.omp/hooks/` and `omp-hooks.md` in sync
- Register a `tool_result` handler whose body is not wrapped in `guarded()` — the
  runner swallows the throw and the hook goes quiet for the rest of the session
- Match a raw `input.path` in a pre hook — strip the anchored-edit content tag
  (`#0D77`) first, or the guard judges a path that exists nowhere
- Gate a command policy on `bash` alone — `eval` carries the same command in
  `input.code`
- Read a pre hook's context parameter — a throw there is promoted to a tool
  failure and the agent loses the call
