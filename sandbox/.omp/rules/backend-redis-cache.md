---
description: Backend Redis cache — TTL reads, invalidation on writes
globs:
      - backend/app/core/cache.py
      - backend/app/routers/*.py
alwaysApply: false
---

# Backend Redis Cache

## Eligibility Standard

Cache only a `GET` response that is deterministic, JSON-serializable, bounded by
explicit query parameters, and materially cheaper to read than to invalidate.

- Use a versioned key in the form `<resource>:v1:<subject-id>:<variant>`.
- The `<subject-id>` is required whenever a response is behind `CurrentUserDep`.
  Include an authorization or permission revision in the scope when permissions can
  change independently of the subject.
- Include every response-shaping parameter in `<variant>` (for example,
  `list:<offset>:<limit>`).
- Set an explicit TTL. The default is 60 seconds; use a shorter TTL only when
  invalidation cannot cover every mutation path.
- Invalidate the entire resource namespace only after a successful create, update,
  or delete transaction. Background jobs that mutate a cached resource must do the
  same.
- Cache misses and Redis unavailability must fall back to the source of truth.
  Cached values must already be JSON-serializable; never cache 4xx/5xx responses.

## Endpoint Decisions

| Endpoint group | Decision | Rationale |
|---|---|---|
| `GET /item/`, `GET /item/{id}` | Cache per authenticated subject | Read responses have bounded keys; item writes invalidate `items:*`. |
| Todo, task, batch reads | Do not cache yet | No hot-read evidence. Add only with the scoped-key and invalidation contract. |
| User reads, `/auth/*`, login tokens | Never cache | Identity, credentials, and session state are security-sensitive. |
| `/health`, SSE, uploads, writes | Never cache | Operational/streaming responses or state changes must be current. |

## Implementation

- Keep the Redis client and JSON operations in `app/core/cache.py`.
- Routers inject `CacheDep` only for scoped cache use and build keys with
  `scoped_cache_key(..., str(current_user.id), ...)`.
- `create`/`update`/`delete` invalidate their resource namespace; read endpoints
  use `get_json` then `set_json(..., ttl_seconds=...)` on a miss.

## Validation (Post-Hook)

`check-backend-redis-cache.ts` verifies subject-scoped keys plus, **per endpoint
that injects `CacheDep`**:

- a `GET` endpoint sets `ttl_seconds=` on its `set_json` — a cached read without
  a TTL never expires;
- a `POST`/`PUT`/`PATCH`/`DELETE` endpoint calls `cache.invalidate()` — a write
  that skips invalidation serves stale data until the TTL runs out.

Per endpoint, not per file: a file-level substring check passes as long as one
sibling endpoint does it, so a new write endpoint could forget invalidation.

## Connection Health

`Redis.from_url(..., health_check_interval=<s>)`. A pooled connection killed
during a failover is otherwise handed to a request and fails it — once per
connection in the pool, which reads as random errors long after the failover.

## Never Do These

- Share an authenticated response under a global cache key.
- Cache user records, authentication responses, tokens, health checks, streams,
  uploads, writes, or error responses.
- Skip invalidation after a successful mutation.
