---
description: Decks sync — harness changes must be reflected in decks/*/slides.md
globs:
      - .omp/rules/*.md
      - .omp/hooks/**/*.ts
      - .omp/ast-grep/rules/**/*.yml
      - .omp/extensions/**/*.ts
      - decks/*/slides.md
alwaysApply: false
---

# Decks Sync

## Purpose

The presentation decks under `decks/` document the harness itself — rules,
hooks, shared hook libraries, AST rules, and their relationships. When the
harness changes (a rule, hook, shared hook library, or AST rule is
added/renamed), the deck that describes it must be updated in the same change.
A deck that names a rule or hook that no longer exists — or omits one that was
just added — is stale documentation.

Machine-checked by `check-decks-sync.ts` (post hook, cross-cutting).

## Two Checks

The check runs two layers — **mention** (name-level) and **content hash**
(change-level):

| Check | Detects | Mechanism |
|---|---|---|
| Mention | Add/rename/delete of rules, hooks, AST dirs | Artifact name (e.g. `check-backend-auth`) must appear in the deck source |
| Content hash | **Edits to an existing artifact** | `<!-- sync: <name>=<sha256-prefix> -->` comments in the deck record each artifact's content hash; mismatch = stale deck |

A mention is a substring match of the artifact name anywhere in the deck's
`slides.md` source. The mention check is **additive** — it only flags artifacts
that are missing from the deck, never extra content.

## Content Hash Sync

- `decks/scripts/sync-hashes.mjs` (run by `make build` in `decks/`) writes one
  `<!-- sync: <name>=<hash> -->` comment per artifact after the headmatter:
  - rule files: `<file>.md`
  - pre/post hooks: `<file>.ts`
  - shared hook libraries: `lib/<file>.ts`
  - AST rule dirs: `ast-grep/rules/<dir>/` (hash of combined YAML content)
- `check-decks-sync.ts` requires a hash comment for **every** live artifact,
  then recomputes it: mismatch → “changed since deck was synced”; missing →
  “no sync hash”; removed → “no longer exists in .omp/”.
- The comments are HTML comments — invisible in the rendered deck
- `make build` refreshes hashes **and** regenerates HTML in one step

## Deck Coverage Map

| Deck | Covers |
|---|---|
| `decks/harness-rules/slides.md` | All rules, all hooks, all AST rule dirs |
| `decks/omp-harness/slides.md` | Harness overview (`.omp/` structure) — not artifact-exhaustive |

Only `decks/harness-rules/slides.md` is artifact-exhaustive and checked. Other
decks are free-form.

## Workflow

1. Add/rename/delete a rule, hook, or AST rule in `.omp/`
2. Update `decks/harness-rules/slides.md` in the **same change** — add/rename
   the artifact name in the relevant table or diagram
3. Run `make build` in `decks/` — refreshes the sync hashes and regenerates HTML
4. Run `make verify` (or `make check-decks-sync`) — the check flags any
   artifact the deck no longer mentions, and any artifact whose content hash
   drifted

## Extensions

An extension under `.omp/extensions/<name>/` is **auto-loaded session
behaviour** — nothing invokes it, so a reader of the deck is the only one who
learns it exists. The mention check therefore covers the directory name, and its
combined `*.ts` content is one artifact hash (`extensions/<name>/`).

## Never Do These

- Change a rule/hook/AST rule name without updating the deck that names it
- Add a new rule/hook/AST rule without adding it to the deck's tables
- Delete a rule/hook/AST rule while the deck still names it (stale doc)
- Edit a rule/hook/AST rule without running `make build` in `decks/` (stale hash)
- Hand-edit the `<!-- sync: ... -->` comments — run `make build` instead
- Put artifact-exhaustive content in a deck other than `harness-rules`
