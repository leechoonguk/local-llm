---
description: Backend ownership — created_by verification on user-scoped resources
globs:
      - backend/app/services/*.py
alwaysApply: false
---

# Backend Ownership

## Purpose

User-scoped resources must verify the caller owns the resource.

## Standard

- Service methods take `current_user` and verify `created_by == current_user.username`
- `403` when the row exists but belongs to someone else — raised as a core exception
  from `app/core/exceptions.py` and mapped by the one handler layer (`rule://backend-exceptions`).
  No such exception exists yet, because no resource in this app is owner-scoped: the
  first one that is adds it there, never an `HTTPException` in a service
- Applies to get/update/delete of user-scoped resources

## Validation (Post-Hook)

`check-backend-ownership.ts` verifies ownership checks exist when a service
method takes `current_user`.

## Where the Check Lives

The comparison belongs in the service that loads the row. A router that does it
instead states a rule the service does not know it has: a batch job, another
service, or a second endpoint reaches the same data without it.
`ast-grep/rules/ownership-router/router-check.yml` runs against `app/routers/` even
when the service side is dormant - a router doing the check itself is exactly
the case where no service method takes `current_user`.

## Never Do These

- Return another user's resource without an ownership check
- Check ownership in the router — it belongs in the service
