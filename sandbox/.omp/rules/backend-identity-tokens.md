---
description: Backend identity tokens — CurrentUserDep injected below the router layer, injected while the edit is being written
condition: "current_user: CurrentUserDep"
scope: "tool:edit(backend/app/services/*.py), tool:write(backend/app/services/*.py), tool:edit(backend/app/repositories/*.py), tool:write(backend/app/repositories/*.py), tool:edit(backend/app/batch/*.py), tool:write(backend/app/batch/*.py)"
interruptMode: always
alwaysApply: false
---

# Backend Identity Tokens

This text arrives because the edit currently being written injects
`current_user: CurrentUserDep` below the router layer.

## current_user: CurrentUserDep

Identity enters at the edge. `CurrentUserDep` resolves an HTTP request's bearer
token, so a service or repository that injects it can no longer be called by a
batch job, a test, or another service — and it hides that a caller's identity
reached that far down.

Pass what the callee actually needs instead:

```python
# app/routers/user.py — identity resolved once, at the edge
async def delete_user(user_id: UUID, user_service: UserServiceDep, current_user: CurrentUserDep) -> None:
    await user_service.delete(user_id, actor_id=current_user.id)
```

An ownership check then belongs in the service, on the plain value
(`created_by != actor_id` → `ForbiddenError`). Details: `rule://backend-auth`
and `rule://backend-ownership`.

## Enforcement

`check-backend-auth` runs
`ast-grep/rules/conventions/current-user-router-only.yml` over the backend app
after the edit lands; this injection is the same invariant delivered before it
does.
