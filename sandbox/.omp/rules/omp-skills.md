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
| `integration` | User asks to integrate an external API, add a provider or operation, or change an integration's fields, paging, or response contract | `make check-api-flow` runs every `api/*.http` against the live stack and reports state neutral | active |
| `slidev` | User asks to create or present a technical slide deck | `make build` succeeds in `decks/` | active |
| `screen-check` | User asks to verify, fix, or refine anything visible in the web UI - layout, spacing, click behaviour, dialogs, grids | A browser run reports the before/after numbers for the changed surface, taken from a fresh entry with a real pointer; `make verify` green | active |

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
