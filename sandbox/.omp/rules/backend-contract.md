---
description: Backend reachability — every service surface is reachable from a router, a batch job or the lifespan
globs:
      - backend/app/dependencies/services.py
      - backend/app/services/**/*.py
      - backend/app/repositories/**/*.py
alwaysApply: false
---

# Backend Contract

## Purpose

The frontend has had this check since the api layer was written:
`check-frontend-contract` refuses a transport function no hook calls and a hook
no screen renders, because **a feature that was never built looks exactly like a
finished one from inside its own layer**. The backend had no counterpart, so
that shape survived here — measured: two `*ServiceDep` aliases nobody injected,
kept alive by `backend-domain` demanding one per domain.

`check-backend-contract` is the backend half.

## What Counts As A Caller

An entry point is what the outside world can start:

| Entry point | Reaches |
|---|---|
| a router endpoint | services, through an injected `*ServiceDep` |
| a scheduled batch job | services, constructed as `Service(session)` (rule://backend-batch) |
| the lifespan | services it calls directly (`list_enabled_batches`, `update_interrupted_runs`) |

**Tests are not callers.** A method whose only caller is its own test is the
exact thing this check exists to find; counting tests would make the check
agree with every dead method that someone was careful enough to cover.

## The Two Rules

- **A DI alias is injected somewhere.** `Annotated[X, Depends(...)]` has exactly
  one consumer — an endpoint signature. An alias no router mentions is a wire to
  a socket that was never installed.
- **A public method beyond the CRUD template has a caller in `app/`.**
  `get`/`list`/`create`/`update`/`delete` are required of every domain by
  `rule://backend-domain`, router or not, so the template explains them. Anything
  past them — `find_checkpoint`, `count_users`, `update_interrupted_runs` — was
  written for a purpose, and one nothing can reach is a purpose that never landed.

Matching reads `.name`, not `.name(`: a `@property` is used without parentheses
(`integration_operation_service.last_call_id`), and requiring the call form
reported every property in the tree as dead.

## The Pair It Forms With `backend-domain`

The two rules point in opposite directions and meet exactly:

| Rule | Direction |
|---|---|
| `backend-domain` | a domain whose **router injects a service** must declare that service's factory and alias |
| `backend-contract` | an alias that **no endpoint injects** must not exist |

Together they read: *declare exactly the aliases your endpoints use.* Before the
pair existed, `backend-domain` required an alias for every domain including the
router-less ones (`barcode`, and the `batch_checkpoint` leaf of the `batch`
domain), which is dead code the rule itself mandated.

## Never Do These

- Keep a service method alive "for later" — later is a commit, and git remembers
  the deleted one.
- Add a router endpoint solely to satisfy this check. An endpoint is a published
  surface with an `api/*.http` block, a frontend caller and an auth story
  (`rule://backend-api-http`, `rule://frontend-contract`); reaching for one to
  silence a warning publishes an unfinished feature.
- Count a test as a caller by importing a service into `app/` from test code.
