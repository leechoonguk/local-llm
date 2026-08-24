---
description: Backend transactions — session.begin() placement rules
globs:
      - backend/app/services/*.py
      - backend/app/repositories/*.py
      - backend/app/routers/*.py
      - backend/app/dependencies/*.py
alwaysApply: false
---

# Backend Transactions

## Rules

1. **`session.begin()` only in service classes** — never in
   routers/repositories/dependencies/batch (checked by `transaction/service-only.yml`,
   scans non-service dirs including `app/batch/`). The rule matches a bare
   `session.begin()`, `self.session.begin()`, **and any aliased holder**
   (`svc.session.begin()`): reaching the transaction through a service handle is
   the same violation.
2. **Within services, only in `create`/`update`/`delete` methods** — never in
   read methods (`get`/`list`/`find_stale`) (checked by
   `domain/service-transaction-write-only.yml`)
3. **`async with self.session.begin():`** — auto commit/rollback, never manual
   `session.commit()`/`session.rollback()` in services

## Why

- Services own the transaction boundary — repositories are stateless
  (they receive the session and operate within the caller's transaction)
- Read methods don't need a transaction — a plain query is fine
- `async with` guarantees rollback on exception (e.g. `NotFoundError`)

## Example

```python
async def create_item(self, data: ItemCreateRequest, created_by: str) -> Item:
    internal = ItemCreateInternal(**data.model_dump(), created_by=created_by)
    async with self.session.begin():
        return await self.item_repository.create(internal)

async def get_item(self, item_id: UUID) -> Item:
    item = await self.item_repository.get(item_id)  # no session.begin()
    if item is None:
        raise NotFoundError(item_id)
    return item
```

## Never Do These

- `session.begin()` in routers/repositories/dependencies
- `session.begin()` in service read methods
- Manual `session.commit()`/`session.rollback()` — use `async with`
