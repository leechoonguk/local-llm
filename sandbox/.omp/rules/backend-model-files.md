---
description: Backend model files — one table, one model class, one file named after the table
globs:
      - backend/app/models/**/*.py
      - .omp/hooks/lib/backend-model-files.ts
alwaysApply: false
---

# Backend Model Files

## The Rule

**One table, one model class, one file, named after the table. A domain that
owns more than one table keeps its files in `models/<domain>/`.**

```
backend/app/models/
  base.py                      # declarative base + mixins — declares no table
  user.py                      # class User  → table user
  batch.py                     # class Batch → table batch
  integration/                 # a domain with five tables → a folder
    provider.py                # class Integration          → table integration_provider
    secret.py                  # class IntegrationSecret     → integration_secret
    operation.py               # class IntegrationOperation   → integration_operation
    field.py                   # class IntegrationField       → integration_field
    call.py                    # class IntegrationCall        → integration_call
```

**Inside the folder the file is named after its table with the domain prefix
dropped.** The path already says `integration`, so
`integration/integration_provider.py` says it twice; the checker reads the
table name back as `<folder>_<file>`.

**One file stays flat.** `user` owns one table, so `models/user.py` is the whole
domain — a folder holding one file adds a level and says nothing.

`__init__.py` in a domain folder is **empty**. It is a package marker, not a
barrel: re-exporting from it would restore the "one import path for five
tables" shape the split removed.

**A layer holds one shape or the other, never both.** `models/user.py` beside
`models/user/` gives "which files does this domain own" two answers, and the
one that answers first wins silently — measured: with both present every check
passed while the flat file's table went unread. Finish the move and delete the
flat file (`check-backend-domain` enforces this for `models/`, `schemas/`,
`repositories/`, and `services/`).

A file with no `__tablename__` is not a table file and is exempt — `base.py`
qualifies by measurement rather than by name.

## Why, Measured

Four integration tables shared `models/integration.py`, and **every reader of
models had to special-case that filename**:

- `check-backend-domain` excluded it from the model AST rules, with the comment
  "the integration aggregate contains SQLAlchemy relationships" — the field rule
  simply did not know `relationship()`, so a whole file was skipped to hide one
  narrow rule;
- `checkDomainStructure` treated a model file as a domain, so `integration` needed
  a hardcoded skip, and the `__tablename__` had to equal the domain name — which
  is why four tables could not each have a file in the first place;
- the file reached 261 lines holding five unrelated schemas.

Splitting removed all three: the field rule learned `relationship()` instead of
skipping a file, and a **domain** became what it always was — the stack whose
`services/<name>.py` exists, owning `models/<name>.py` or `models/<name>/*.py`.
No exception list survives.

The folder came second, and for a different reason: five flat
`integration_*.py` files sat in a directory every other domain has one file in,
so a reader had to reconstruct the grouping from the prefix and a checker had to
match on it. The folder states it once.

## What Follows From It

- **A domain may own many tables.** `integration` owns five. Domain discovery
  reads `services/`, never `models/`, so a new table is a new file and nothing
  else.
- **File names are lower snake case**, because they are table names
  (`integration_call` → `integration/call.py`), not identifiers.
- **Imports point at the owner.** A file that needs another table's FK string
  imports it from that table's module (`from app.models.integration.operation
  import OPERATION_FK`), so the dependency is visible and acyclic:
  provider ← secret ← operation ← field/call.
- **Back-references use `TYPE_CHECKING`.** A parent annotates children it cannot
  import at runtime; SQLAlchemy resolves the relationship through its registry
  once every module is imported (`alembic/env.py`, `tests/conftest.py` import all
  of them, and `check-backend-domain` checks that per file — a table nobody
  imports is absent from the metadata, so autogenerate writes an empty migration).
- **Shared model constants live in `base.py`** (`CHILD_CASCADE`), not duplicated
  per file.
- **The same shape applies to the other layers.** `repositories/<domain>/`
  (`backend-repository-files.md`) and `schemas/<domain>/` follow the identical
  rule, so one domain reads the same way down the stack.

## Validation (Post-Hook)

`check-backend-model-files` reads `backend/app/models/`, one level into domain
folders:

| Check | Fires when |
|---|---|
| one table per file | a file declares two `__tablename__` values |
| named after its table | the file name and `__tablename__` disagree — inside a folder the expected name is `<folder>_<file>` |
| one mapped class per file | a file declares two classes inheriting `Base` |
| a multi-table domain uses a folder | two or more flat `<domain>_*.py` files exist instead of `models/<domain>/` |

## Never Do These

- Put two tables in one model file.
- Name a model file something other than its table.
- Repeat the domain prefix inside its own folder
  (`integration/integration_provider.py`).
- Leave a domain's second table as a flat sibling — move both into the folder.
- Add a filename to an exception list in a hook because a model file is "special".
- Re-export a model from a barrel module to keep old imports working — move the
  imports instead.
