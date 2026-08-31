---
description: Backend repository files — one repository, one table, named after it; a full-entity select of another table belongs in that table's own file
globs:
      - backend/app/repositories/**/*.py
      - .omp/hooks/lib/backend-repository-files.ts
alwaysApply: false
---

# Backend Repository Files

## The Rule

**One repository, one table, named after it. A domain with more than one
repository keeps them in `repositories/<domain>/`.** A repository file's own
queries — `select(Model)`, bare, never a dotted column — must target the table
its filename names.

```
repositories/
  user.py                UserRepository  → table user
  batch.py               BatchRepository → table batch
  integration/           # three repositories → a folder
    provider.py          IntegrationProviderRepository  → integration_provider
    secret.py            IntegrationSecretRepository    → integration_secret
    operation.py         IntegrationOperationRepository → integration_operation
```

Inside the folder the file drops the domain prefix, and the checker reads the
table back as `<folder>_<file>` — the same shape as `models/<domain>/`
(`backend-model-files.md`), so one domain reads identically in both layers.

## The Proxy Is Measured, Not Guessed

`repositories/integration.py` (before the split) had **three** distinct bare
`select()` targets in one file — `Integration`, `IntegrationOperation`,
`IntegrationSecret` — because the aggregate's provider queries, its operation
lookup, and its secret CRUD all lived together. That is the defect: a table's
own persistence logic is not where its filename says to look for it.

**A column projection is not this rule.** `count_secret_references` runs
`select(IntegrationField.id).where(IntegrationField.secret_id == secret_id)`
inside `integration_secret.py` — a referential-integrity check ("is this secret
still used") before a delete, not `IntegrationField`'s CRUD hosted in the wrong
file. The rule reads `select(Model)` and exempts `select(Model.column)`.

**Constructing another table's row is not this rule either.** The provider
repository's `create`/`update` build `IntegrationOperation(...)` and
`IntegrationField(...)` instances and assign them into a relationship
(`operations=[...]`) inside one aggregate-root transaction — that is assembly,
and SQLAlchemy's cascade performs the inserts. The repository never calls
`select` on those tables to do it.

## Not Every Table Has a Repository File

`IntegrationField` has none. Every field row is created inside the provider
aggregate's `create`/`update`; there is no direct field query or command
anywhere in the codebase. A file with one method nobody calls is exactly the
kind of scaffolding the completeness contract forbids — the file exists the day
a caller needs one, not before.

## Validation (Post-Hook)

`check-backend-repository-files` reads `backend/app/repositories/`, one level
into domain folders:

| Check | Fires when |
|---|---|
| named after its table | the file's table name (`<folder>_<file>` inside a folder) is not a table any model file declares |
| queries only its own table | a bare `select(Model)` targets a table other than the file's own |
| one repository class per file | a file declares two classes that take a `session` |
| a multi-repository domain uses a folder | two or more flat `<domain>_*.py` files exist instead of `repositories/<domain>/` |

## Never Do These

- Put a second table's `select(Model)` (bare, whole-entity) in a repository
  that is not that table's own file.
- Name a repository file after anything but the table it queries.
- Declare two repository classes in one file.
- Create an empty repository file for a table nothing queries directly yet.
- Leave a domain's second repository as a flat sibling — move both into the
  folder.
