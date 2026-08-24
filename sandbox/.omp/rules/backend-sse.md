---
description: Backend SSE — EventSourceResponse (fastapi.sse), AsyncIterable return
globs:
      - backend/app/routers/*.py
alwaysApply: false
---

# Backend SSE

## Purpose

Server-Sent Events via the FastAPI official EventSourceResponse.

## Standard

Per FastAPI docs (`fastapi.sse`), NOT raw `StreamingResponse`:

```python
from collections.abc import AsyncIterable
from fastapi.sse import EventSourceResponse, ServerSentEvent

@app.get("/items/stream", response_class=EventSourceResponse)
async def stream_items() -> AsyncIterable[ServerSentEvent]:
    yield ServerSentEvent(comment="stream of item updates")
    for i, item in enumerate(items):
        yield ServerSentEvent(data=item, event="item_update", id=str(i + 1), retry=5000)
```

- Return type `AsyncIterable[ServerSentEvent]` — Pydantic validates/serializes
  on the Rust side (higher performance)
- `ServerSentEvent` fields: `data`, `event`, `id`, `retry`, `comment`
- FastAPI sends a keep-alive ping comment every 15s of inactivity, sets
  `Cache-Control: no-cache` and `X-Accel-Buffering: no` automatically
- Client disconnect handled by the generator's `finally`

## Validation (Post-Hook)

`check-backend-sse.ts` verifies SSE endpoints use EventSourceResponse.

## Never Do These

- Implement SSE with raw `StreamingResponse` — use `EventSourceResponse`
- Skip the `AsyncIterable[ServerSentEvent]` return type
