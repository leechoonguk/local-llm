---
description: Backend service-boundary tokens — transactions, raw streaming, and bare tasks outside the service layer, injected while the edit is being written
condition: "async with [\\w.]*session\\.begin\\(|return StreamingResponse\\(|asyncio\\.create_task\\(|\\bhttpx2\\b"
scope: "tool:edit(backend/app/routers/*.py), tool:write(backend/app/routers/*.py), tool:edit(backend/app/repositories/*.py), tool:write(backend/app/repositories/*.py), tool:edit(backend/app/batch/*.py), tool:write(backend/app/batch/*.py)"
interruptMode: always
alwaysApply: false
---

# Backend Service Boundary Tokens

This text arrives because the edit currently being written puts a
service-layer-only construct in a router, repository, or batch job.

The trigger matches each construct, not its name: `batches.py` carries a comment
saying "No session.begin()/commit() here", and an interrupting rule that fires
on the comment explaining the ban is worse than no rule.

## session.begin()

Transaction boundaries live in **services only** — one `async with
self.session.begin():` per write operation. A router or repository that opens a
transaction either nests one inside the service's own or commits work the
service did not decide to commit. Move the call into the service method.
Details: `rule://backend-transaction`.

## StreamingResponse()

SSE endpoints return `EventSourceResponse` yielding `ServerSentEvent`, never a
raw `StreamingResponse`: the raw form drops the `text/event-stream` framing
(`event`, `id`, `retry`) that clients reconnect with. Details: `rule://backend-sse`.

## asyncio.create_task()

A bare task is unawaited, unlogged, and dies with the request. Use FastAPI's
`BackgroundTasks` (`background_tasks.add_task(...)`) so the work is tied to the
response lifecycle. Details: `rule://backend-background-tasks`.

## httpx2

`httpx2` lives in `core/integration.py` and its wiring only (`main.py` owns the
shared client, `dependencies/integrations.py` injects it, `services/integration.py`
passes it through). A second HTTP client anywhere else brings its own timeouts,
retries, and error mapping — the drift `IntegrationClient` exists to prevent.
Call the integration service instead. Details: `rule://backend-integration`.

## Enforcement

`check-backend-transaction`, `check-backend-sse`,
`check-backend-background-tasks`, and `check-backend-integration` fail on these
after the edit lands; this injection is the same invariant delivered before it
does.
