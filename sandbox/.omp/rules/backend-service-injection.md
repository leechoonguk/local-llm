---
description: Backend service injection — a service composes repositories, never another service
globs:
      - backend/app/services/**/*.py
      - .omp/hooks/lib/backend-service-injection.ts
alwaysApply: false
---

# Backend Service Injection

## The Rule

**A service composes repositories. It never composes another service.**

```python
class IntegrationProviderService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.provider_repository = IntegrationProviderRepository(session)
        self.secret_repository = IntegrationSecretRepository(session)
        self.operation_repository = IntegrationOperationRepository(session)
```

One service, three repositories — as many as the use case needs. A service is
not required to map 1:1 to a table or to a repository: it exists for the use
case that needs it, and a use case that touches a five-table aggregate injects
five repositories into one service rather than being split into five services
that would each need to talk to the others.

## Why

This repo's services each own their transaction: `async with
self.session.begin(): ...` is the one boundary a reader checks. A service
holding another service could call one of its methods and open a **second**
`session.begin()` on the same session mid-call, or run business logic through
two owners with no single place that boundary lives. Repositories never begin
a transaction; only a service does, so a service that only ever holds
repositories is a service with one owner of its transaction.

## Validation (Post-Hook)

`check-backend-service-injection` reads every file in `backend/app/services/`
for one thing: **no import from `app.services`.** That single check covers both
shapes a service-to-service dependency could take — a typed constructor
parameter (`user_service: UserService`) and an untyped construction
(`self.user_service = UserService(session)`) — because neither is possible without
importing the class first.

## Never Do These

- Import a class from `app.services.<anything>` inside `app/services/`.
- Type-hint or construct another service inside a service's `__init__`.
- Give a service a use case it does not have a repository for — inject the
  repository the use case needs, not a service that already has one.
