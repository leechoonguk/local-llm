---
description: Backend external API transport — database-resolved IntegrationClient, retry, error mapping
globs:
      - backend/app/core/integration.py
      - backend/app/core/exceptions.py
      - backend/app/dependencies/integrations.py
      - backend/app/main.py
alwaysApply: false
---

# Backend External API Integration

## Purpose

This rule governs the transport path for outbound HTTP calls. Database table
ownership, schemas, and field mappings are governed by
`backend-integration-configuration.md`; this rule keeps retry, timeout, shared
client lifecycle, and exception behavior uniform.

## Architecture

```
Service layer → IntegrationClient.from_database() → IntegrationClient.execute()
              → shared httpx2.AsyncClient → external API
```

- `IntegrationClient` is the only external HTTP execution path. Raw
  `httpx2`/`requests`/`aiohttp` calls outside `app/core/integration.py` are forbidden.
- The lifespan owns one shared `httpx2.AsyncClient`, exposed through
  `IntegrationHttpClientDep`; clients receiving it never close it.
- `from_database()` resolves one enabled provider/operation configuration and
  `execute()` renders it. Callers cannot supply a URL or raw headers.
- The inbound `X-Request-ID` is always propagated and cannot be overridden by
  DB configuration.

## Transport Contract

| Concern | Standard |
|---|---|
| HTTP client | `httpx2.AsyncClient`, async only |
| Timeouts | operation `connect_timeout_ms` and `read_timeout_ms` |
| Retries | operation `max_retries`, exponential backoff plus jitter, capped by `retry_max_ms` |
| Retry scope | configured `idempotent=true` only |
| Retry triggers | network errors, timeouts, 429, 500/502/503/504 |
| 429 handling | honor standard `Retry-After`, capped by retry maximum |
| Error mapping | `IntegrationError` 502, `IntegrationTimeoutError` 504, `IntegrationRateLimitError` 429 |
| Result | `IntegrationExecutionResult(canonical_payload, metadata, status_code)` |
| Logging | provider, operation, attempt, status, duration only — never body, header values, or secrets |

## Testing

- Use `httpx2.MockTransport`; never call real external APIs.
- Cover configured request rendering, JSON Schema rejection, response mapping,
  response-header validation, retry success/exhaustion, timeout, network error,
  rate limit, request-ID propagation, and shared-client lifecycle.
- Tests live in `backend/tests/core/test_integration.py`.

## Validation

`check-backend-integration.ts` verifies the transport contract after tool
execution, including **containment**: `httpx2` may appear only in
`core/integration.py` (the client), `main.py` (the lifespan that owns the shared
client), `dependencies/integrations.py` (injection), and `services/integration.py`
(passing it through). Anywhere else it means a second HTTP client with its own
timeouts, retries, and error mapping — the drift `IntegrationClient` exists to
prevent. `check-backend-integration-configuration.ts` separately verifies the
four-table configuration contract.

## Validation (Post-Hook)

| AST rule | Claim |
|---|---|
| `integration/timeout-configured.yml` | the client builds a per-operation `httpx2.Timeout(...)` — the previous regex was satisfied by `except httpx2.TimeoutException` |

## Retry Gating

`max_retries` says **how often** a call may be retried; `operation.idempotent`
says **whether at all**. Retrying a non-idempotent operation repeats its side
effect - a second charge, a second order, a second message.

`check-backend-integration` requires every `await self._backoff(...)` to sit
under a condition that reads `self.operation.idempotent`. A file-level check for
the word would pass while one branch quietly lost its guard.

## Pool Ceiling

The shared client carries `httpx2.Limits(max_connections=..., max_keepalive_connections=...)`.
An unbounded pool turns one slow provider into every worker blocked on a socket —
the ceiling is what keeps a provider outage local to that provider.

## Never Do These

- Reintroduce `request()`, `headers=`, caller-provided URL, or `response_model=` APIs.
- Retry a non-idempotent operation.
- Log request/response bodies, header values, API keys, or tokens.
- Construct a per-request HTTP client.
- Swallow integration exceptions instead of mapping them.
