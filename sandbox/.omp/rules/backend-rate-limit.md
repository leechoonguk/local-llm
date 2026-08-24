---
description: Backend rate limiting — slowapi, login/signup protection, 429 handling
globs:
      - backend/app/routers/auth.py
      - backend/app/routers/user.py
alwaysApply: false
---

# Backend Rate Limiting

## Purpose

Protect auth endpoints against brute force with slowapi.

## Standard

- `slowapi`; `@limiter.limit("5/minute")` on `POST /auth/login` and `POST /user/`
- 429 response with `Retry-After` header
- Limiter state stored in `app.state.limiter` (lifespan)

## Validation (Post-Hook)

`check-backend-rate-limit.ts` verifies the limiter is configured and applied
to login/signup when present.

## Never Do These

- Import `limiter` without applying `@limiter.limit` to auth endpoints
- Rate-limit only reads — the attack surface is login/signup
