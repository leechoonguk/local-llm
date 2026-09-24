---
description: Tooling language — checks, runners and scripts are TypeScript under .omp/hooks/ or .omp/extensions/, never Python
globs:
      - .omp/hooks/**/*.ts
      - .omp/extensions/**/*.ts
      - Makefile
      - backend/scripts/**
      - decks/scripts/**
alwaysApply: false
---

# Tooling Language

Automation is read far more often than it is written, and it must run on any
machine that can run the harness. That fixes the language and the location:
**tooling is TypeScript under `.omp/hooks/`, executed by a `make` target.**

Machine-checked by `strict-tooling.ts` (write time) and `check-tooling.ts`
(tree scan).

## Reading the Database

Checking a row has one path: **`psql` inside the postgres container, spawned from
one place.** `make db-query q="SELECT …"` for a human, `query()` in
`lib/backend-api-flow.ts` for the harness — and nothing else.

| Rule | The failure it closes |
|---|---|
| One spawn site in `.omp/hooks/` (`,\s*"psql",` in an argv) | `rowCounts()` built its own `docker compose exec` argv beside `query()`, so the credentials and the container name existed twice while the comment above claimed they did not |
| The form is `docker compose exec -T postgres psql` (any stack's `$(DC…)` variable) | a host `psql` assumes a local client (this machine has none), and `docker exec` by container name bypasses compose's project scoping |
| No driver import (`asyncpg`, `psycopg`, `pg`) in a hook | a second connection path with a second copy of the credentials, invisible to `make db-query` |
| A Makefile target that runs `psql` brings its database to head first (`migrate`, or `alembic upgrade head` in the container) | an answer read from a database behind head is "drift" that is only a missing migration |

**Never check a row through an API endpoint.** Measured: the seeded-operation
drift gate first compared migrations against `GET /integration/`, and a
bare-array response made the live set empty — a live operation was reported as
absent. An endpoint filters, paginates and serialises; that is the right
instrument for behaviour and the wrong one for "does this row exist".

Machine-checked by `check-tooling.ts` (`checkDatabaseAccess`).

## Placement

| Kind | Location | Executed by |
|---|---|---|
| Automatic check | `.omp/hooks/post/check-<name>.ts` | `tool_result` event **and** `make check-<name>` |
| Write-time block | `.omp/hooks/pre/strict-<name>.ts` | `tool_call` event |
| Shared logic / CLI-only runner | `.omp/hooks/lib/<scope>-<name>.ts` | its hook, or `make <target>` |
| Package build script | that package (`decks/scripts/*.mjs`, `frontend/*.config.*`) | that package's Makefile |
| Session-lifetime behaviour | `.omp/extensions/<name>/*.ts` | the extension runner — **auto-loaded**, never invoked |
| Application code | `backend/app`, `backend/tests`, `backend/alembic` | the app, pytest, alembic |

- **Python is application code only.** A Python helper for a check needs a
  virtualenv, a second toolchain and a second dependency set to answer one
  question. `node` already runs the harness, and it strips TypeScript types
  natively — a `.ts` file is directly executable.
- **One sanctioned shell script**: `backend/scripts/start.sh`. Shell has no
  types, no imports and no tests; a second one is an unreviewable check.
- **`.omp/hooks/` is TypeScript only.** Hooks and libs import each other, so a
  stray `.js`/`.mjs` breaks the import graph and the type contract.
- **No root `scripts/`, `tools/`, `bin/`, `utils/`.** Tooling outside
  `.omp/hooks/` is invisible to `check-omp-hooks` (no rule↔hook mapping, no deck
  sync, no contract table) and to `make`, so nothing runs it.
- **No throwaway scripts.** A verification script kept outside the repository
  proves nothing after the session ends: land it as a hook or a lib with a make
  target, or do not rely on it.

## Execution

- Every `check-*` target in the root `Makefile` runs `node .omp/hooks/...` —
  never an interpreter, virtualenv or shell wrapper. A check that needs
  `.venv/bin/python` cannot run before `make install`.
- A runner that mutates state or calls the network (`check-api-flow` →
  `lib/backend-api-flow.ts`) stays **CLI-only**: it is never wired to a
  `tool_result` event, because it must be asked for, not triggered.
- Register the target in the root `Makefile` and `root-makefile.md`, and add the
  hook to `omp-hooks.md` — `check-makefiles` and `check-omp-hooks` enforce both.

## Review Judgement (not machine-checked)

- Verification code kept outside the repository (a temp dir, a home directory).
  Nothing in the repository can see it; the rule exists so a reviewer asks where


## Hooks vs Extensions

Both are TypeScript, both load through the same extension runner, and the split
is by *what the code needs*:

- **`.omp/hooks/`** — a check or a block tied to one tool call. It answers a
  question about the workspace, and `make check-<name>` must be able to run the
  same logic from the CLI. Every hook maps to a rule (`omp-hooks.md`).
- **`.omp/extensions/`** — behaviour that needs the *session*: lifecycle events
  (`session_start`, `session_stop`, compaction), persisted session state
  (`appendEntry`), a registered tool or command, or UI status. This is the
  native auto-discovery root (`<cwd>/.omp/extensions/`), so an extension is
  **loaded automatically and applies without anyone invoking it**.

An extension may be disabled by name without deleting it:
`disabledExtensions: ["extension-module:<dir or file stem>"]`. Hook-capability
modules under `.omp/hooks/` do not honour that key, so anything that must be
switchable belongs here.

## Unattended Verification

An extension that runs a command at settle time has no approval gate in front of
it. Such a command is therefore restricted to an allowlist — `make …`,
`node .omp/hooks/…`, `git status --porcelain`, `git diff --stat` — and anything
else is **reported as rejected, never run**. A verification is a question about
the workspace; if a predicate needs to change the workspace, it is not a
predicate.

## Never Do These

- Write a Python script for a check, a migration helper, a runner or a fixture
  generator outside `backend/app|tests|alembic`
- Add a second shell script, or hide logic in a Makefile recipe instead of a hook
- Put a `.js`/`.mjs` file under `.omp/hooks/` or `.omp/extensions/`
- Let an extension run an unallowlisted command without an approval gate
- Create a root `scripts/`, `tools/`, `bin/` or `utils/` directory
- Run a check through an interpreter or virtualenv instead of `node`
- Keep verification code outside the repository (temp dir, home directory)
- Wire a state-mutating or network-calling runner to a post hook
