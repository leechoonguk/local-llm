---
description: Backend naming — file names, variable names, module-private functions, encapsulation
globs:
      - backend/app/**/*.py
alwaysApply: false
---

# Backend Naming

## File Names

- `<name>.py` — lowercase alphanumeric (`^[a-z][a-z0-9]*$`), no hyphens/underscores/capitals
- The **model filename is the single source of truth** for the domain name:
  schemas/repositories/services/routers must use the same `<name>.py`
  (machine-checked by `check-backend-domain.ts`)

## Service Variable Names (code-wide)

Any local variable, parameter, or attribute holding a service instance is
prefixed with its domain (checked by `naming/var-name.yml`):

| Context | Pattern | Example |
|---|---|---|
| Router param | `<domain>_service: XxxServiceDep` | `item_service: ItemServiceDep` |
| Local var (batch/services) | `<domain>_service = XxxService(session)` | `item_service = ItemService(session)` |
| Batch repository access | `<domain>_service.<domain>_repository.<method>()` | `item_service.item_repository.find_stale(...)` |

Never a bare `service`.

## Service Internals

Every internal collaborator is prefixed with its domain
(checked by `service/repository-param.yml`):

| Member | Pattern | Example |
|---|---|---|
| Own repository | `self.<name>_repository` | `self.item_repository = ItemRepository(session)` |
| Other repository | `self.<other>_repository` | `self.user_repository = UserRepository(session)` |
| Other service | `self.<other>_service` | `self.audit_service = AuditService(session)` |

Never a bare `self.repository`.

## Repository Encapsulation (code-wide)

Repositories are private to their service. Only the owning service (via
`self.<domain>_repository`) may access them. Any
`<domain>_service.<domain>_repository.*` access outside a service class is
forbidden — call the service method instead
(checked by `naming/repository-access.yml`).

## Module-Private Functions

Module-level functions never referenced by another module must be prefixed with
`_` (e.g. `_lifespan`). Inner functions follow the same rule via
`naming/inner-function-underscore.yml`, enforced by `check-backend-naming.ts`.
FastAPI routes (`@router.`/`@app.` decorators), DI factories wired via
`Depends(NAME)`, and imported names are exempt.

## Inner Functions

A function defined inside another function must be named `_<name>`
(e.g. `_not_found_handler`). Machine-checked by
`conventions/inner-function-underscore.yml`.

## Section Dividers

Every module in `backend/app/` is split into labeled sections by divider
pairs (machine-checked by `check-backend-naming.ts`):

```python
# ============================================================
# Imports
# ============================================================

from __future__ import annotations
...

# ============================================================
# Classes
# ============================================================

class Item(Base, AuditMixin):
    ...
```

- Divider = `# ` + 60 `=` characters; the next line is `# <Section Name>`.
- The first section is always `Imports` and precedes any code.
- **Import order, grouping and the blank lines after the block belong to ruff's
  `I` rules** (`lines-after-imports = 2`). Nothing switches the sorter off
  locally: no `# isort: off`/`# isort: on`, no `# noqa: I001`, no
  `# ruff: noqa: I001`. An exemption turns the order from a standard into a
  per-file opinion, and the next reader cannot tell which files were sorted.
- The markers this rule used to *require* were removed. Their premise — that
  isort would absorb the divider comments into the import block — is false,
  measured both ways (banner separated by a blank line, and banner glued to the
  last import): ruff leaves the banner where it is.
- Canonical section order: `Imports` → `Constants` → `Classes` → `Functions`
  → `Dependencies` → `Router` → `Middleware` → `Lifespan` → `App Setup` →
  `Router Registration`.
- A section is included only when the file has that content; the included
  sections must appear in canonical order (e.g. `Imports` → `Classes` →
  `Functions`, never `Functions` before `Classes`).
- `main.py` uses the app-level sections: `Middleware`, `Lifespan`,
  `App Setup`, `Router Registration`.
- Routers use `Router` (the `router = APIRouter(...)` block) instead of
  `Classes`/`Functions`; dependencies use `Dependencies` for the
  `Annotated[...]` aliases.

## Never Do These

- Bare `service` variable/param — domain-prefix it
- Bare `self.repository` — domain-prefix it
- Repository access outside the owning service
- Module-private functions without `_` prefix
- Inner functions without `_` prefix
- Non-lowercase/non-alphanumeric file names
- A module without section dividers, or a first section other than `Imports`
- A section name outside the canonical set, or sections out of canonical order
- Code before the first `# Imports` divider
