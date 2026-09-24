---
description: OMP skills catalog and discovery conventions
globs:
      - .omp/skills/*/SKILL.md
      - .omp/rules/omp-skills.md
alwaysApply: false
---

# OMP Skills Governance

## Runtime Contract vs Project Governance

OMP discovers skills only from `.omp/skills/<name>/SKILL.md`; explicit `name`
and `description` are runtime metadata. The catalog below is **project
governance** for authoring and verification. Its Trigger, Verification, and
Lifecycle columns do not change OMP discovery, prompt exposure, `skill://`, or
`/skill:` behavior.

## Skill Catalog

| Skill | Trigger | Verification | Lifecycle (project metadata) |
|---|---|---|---|
| `commit` | User asks to commit, push, publish, or prepare a verified commit | Root `make verify` succeeds before Git commit or push | active |
| `integration` | User asks to integrate an external API, add a provider or operation, or change an integration's fields, paging, or response contract | `make check-api-flow` runs every `api/*.http` against the live stack and reports state neutral; a paging operation hands off to `ledger` (`check-backend-batch` names the missing `Feed`) | active |
| `ledger` | User asks to migrate an external feed into a table, add a sync batch job for a provider operation, or extend an existing ledger | A live pass reports rows received and written, a second pass reports `written = count(*)` with every `id` unchanged and `max(version) = 1`; `make verify` green | active |
| `slidev` | User asks to create or present a technical slide deck | `make build` succeeds in `decks/` | active |
| `screen-check` | User asks to verify, fix, or refine anything visible in the web UI - layout, spacing, click behaviour, dialogs, grids | A browser run reports the before/after numbers for the changed surface, taken from a fresh entry with a real pointer; `make verify` green | active |

## Skill Harness (`enforced-by`)

A skill's peculiar invariants must answer to a mechanical check that runs in
the root `make verify` — a skill whose rules live only in prose is a check
nobody runs. The contract is three-way and **name-driven**, held by
`check-omp-skills`:

| Leg | Statement | Failure |
|---|---|---|
| Naming | a post hook whose hyphenated name contains the skill's name contiguously (`ledger` → `check-backend-ledger`) **is** that skill's harness — ownership is read off the filename, no marker comment to drift | a hook named after a skill the skill does not declare |
| Declaration | `SKILL.md` frontmatter carries `enforced-by:` listing exactly the name-derived set (`[]` for a procedure skill) | key absent; a declared hook that does not exist or whose name does not carry the skill's |
| Gate membership | every declared hook's `check-*` target is a prerequisite of the root `verify` | a harness outside the gate |

A **procedure skill** (commit, screen-check, slidev) owns no hook: it declares
`enforced-by: []` and must reference at least one `rule://` domain in its body
— the rulebook domain that carries the enforcement it relies on. A **domain
skill** (ledger, integration) names its harness, and a new check for a skill's
invariant is therefore a post hook named after the skill, wired into `verify`,
and declared in the frontmatter — all three in the same change.

## Catalog Conventions

- Every direct child of `.omp/skills/` with a `SKILL.md` has exactly one row.
- Each `SKILL.md` declares an explicit `name` equal to its directory name and a
  non-empty `description` in YAML frontmatter.
- Every row supplies a concrete trigger, verification command or observable,
  and lifecycle (`active` or `deprecated`).
- Lifecycle is documentation-only project metadata. `deprecated` does not hide,
  disable, or remove a discovered skill; retain its file and row until an
  explicit clean cutover removes both.
- Add or remove a skill and its catalog row in the same change.
- Run `make check-omp-skills`; it validates the catalog bidirectionally against
  the discovered skill files. `make verify` includes this check.

## Adding a New Skill

1. Create `.omp/skills/<name>/SKILL.md` with explicit `name` and `description`
   frontmatter. Keep assets under that same skill directory.
2. Add one `active` row to **Skill Catalog** with a precise user trigger and
   verification command or observable outcome.
3. Add the skill-specific workflow to `SKILL.md`; skills document behavior and
   hooks enforce only policies that must run at tool boundaries.
4. Run `make check-omp-skills`, then `make verify`.

## Never Do These

- Create nested skill directories; native discovery scans only one level below
  `.omp/skills/`.
- Add a skill without catalog metadata or a catalog row without its `SKILL.md`.
- Use a catalog row as a replacement for the skill frontmatter description.
- Assume `deprecated` changes a skill's OMP runtime availability.
