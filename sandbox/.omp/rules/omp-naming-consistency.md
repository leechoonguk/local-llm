---
description: Naming consistency — rule/hook names must match their actual scope (prefix ↔ globs ↔ paths)
globs:
      - .omp/rules/*.md
      - .omp/hooks/**/*.ts
alwaysApply: false
---

# Naming Consistency

## Purpose

A rule or hook name must reflect what it actually governs. A `backend-*` rule
that reads root files, or a `check-frontend-*` hook that touches `backend/`
paths, is a name–scope mismatch that misleads maintainers and hides where a
change belongs. This rule defines the machine-checkable half of that contract:
**name prefix ↔ path scope**.

This prefix map is **project governance**. OMP exposes rule globs as metadata
and only uses them as a runtime path gate for TTSR; it does not infer scope
from file-name prefixes.

Semantic drift (e.g. a rule named `backend-domain` that silently drops the
router section) cannot be checked mechanically — that stays a review concern.
Structural drift (name says one scope, globs/paths touch another) is checked
by `check-omp-rules.ts` (rules) and `check-omp-hooks.ts` (hooks).

## Scope Prefix ↔ Path Mapping

| Name prefix | Must govern | Example |
|---|---|---|
| `backend-` | `backend/` paths | `backend-domain.md` → globs `backend/app/**` |
| `frontend-` | `frontend/` paths | `frontend-code-conventions.md` → globs `frontend/src/**` |
| `omp-` | `.omp/` paths | `omp-hooks.md` → globs `.omp/hooks/**` |
| `root-` | root-level files (`Makefile`, `docker-compose.yml`, `.env*`) | `root-makefile.md` → globs `Makefile` |
| *(none)* | cross-cutting — globs span ≥2 top-level dirs | `environment.md` → `.env*` + `backend/.env*` |

## Rule Checks (check-omp-rules.ts)

For every rule file in `.omp/rules/`:

1. **Prefix ↔ globs**: a `backend-`/`frontend-`/`omp-`/`root-` rule must have at
   least one glob starting with the matching top-level directory
   (`backend/`, `frontend/`, `.omp/`, or a root-level file for `root-`).
2. **Cross-cutting**: a prefix-less rule must have globs spanning ≥2 top-level
   directories (already enforced — this rule documents the intent).

## Hook Checks (check-omp-hooks.ts)

For every hook file in `.omp/hooks/`:

1. **Name ↔ paths**: a `check-backend-*`/`strict-backend-*` hook must reference
   `backend` paths in its code; `check-frontend-*`/`strict-frontend-*` must
   reference `frontend`; `check-omp-*`/`strict-omp-*` must reference `.omp`.
2. **Cross-cutting**: prefix-less hooks (`check-makefiles`, `check-verify`,
   `strict-command-routing`, `strict-no-subagents`) are exempt — they span
   multiple scopes by design.

## Adding a New Rule or Hook

1. Pick the prefix that matches the scope you actually govern
2. If it spans root + backend (or any 2+ top-level dirs), omit the prefix
3. Keep globs (rules) and path references (hooks) inside that scope
4. Run `make verify` — the naming checks flag any mismatch

## Never Do These

- Name a rule `backend-*` but give it root-level globs (or vice versa)
- Name a hook `check-backend-*` but read `frontend/` or root paths
- Add a cross-cutting rule/hook with a scope prefix — omit it instead
- Rename a rule/hook without updating its globs/paths to match
