---
description: Backend background tasks — BackgroundTasks pattern, app/tasks/ placement
globs:
      - backend/app/**/*.py
alwaysApply: false
---

# Backend Background Tasks

## Purpose

Post-response work (email, cleanup) via FastAPI BackgroundTasks.

## Standard

Per FastAPI docs:

```python
@app.post("/send-notification/{email}")
async def send_notification(email: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(write_notification, email, message="some notification")
    return {"message": "Notification sent in the background"}
```

- Task function in `app/tasks/`; never block the response on the task
- Never use raw `asyncio.create_task` for request-scoped work

## Validation (Post-Hook)

`check-backend-background-tasks.ts` verifies BackgroundTasks usage when present.

## Never Do These

- `asyncio.create_task` in routers — use BackgroundTasks
- Block the response on the task
