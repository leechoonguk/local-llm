---
description: Backend middleware — CORS, CSRF protection, security headers, request ID, structured logging, trusted hosts
globs:
      - backend/app/main.py
      - backend/app/core/logging.py
      - backend/tests/api/test_middleware.py
alwaysApply: false
---

# Backend Middleware

## Purpose

Standard middleware stack for the FastAPI app. All middleware is registered
in `main.py` via `app.add_middleware(...)` (or `@app.middleware("http")` for
custom ones). Verified against FastAPI official docs (Context7).

## Required Middleware

### 1. CORS

Per FastAPI docs (`CORSMiddleware`):

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # dev: ["http://localhost:25173"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- `allow_origins` from settings; dev includes `http://localhost:25173` (Vite)

### 2. CSRF Protection

`CsrfProtection` validates every unsafe method (`POST`, `PUT`, `PATCH`,
`DELETE`) before it reaches a route:

- A present `Origin` must be listed in `settings.cors_origins`; `*` is never a
  trusted CSRF origin.
- `Sec-Fetch-Site: cross-site` is rejected unless the request has an explicitly
  trusted Origin. Safe methods (`GET`, `HEAD`, `OPTIONS`) are never blocked.
- Rejections return `403 {"detail": "CSRF validation failed"}` and vary by
  `Origin` and `Sec-Fetch-Site`.
- Requests without browser origin metadata remain compatible with API clients
  that explicitly send Bearer credentials.

This API uses Bearer tokens, not cookies; browsers do not attach Bearer headers
automatically, so no CSRF token is issued. If cookie-backed authentication is
introduced, add a session-bound synchronizer token or signed double-submit
token before accepting authenticated unsafe requests.

### 3. Security Headers

Custom `SecurityHeaders` middleware (`@app.middleware("http")`) sets:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- `X-XSS-Protection: 1; mode=block`

### 4. Request ID

- Middleware reads `X-Request-ID` header or generates `uuid4()`
- Sets the response header `X-Request-ID`
- Passes the id into the logging context

### 5. Structured Logging

- `structlog` configured in `app/core/logging.py`; JSON renderer in production
- Request logging middleware logs method, path, status, duration_ms, request_id
- Never `print()` for application logging

## Optional Built-ins (FastAPI)

- `TrustedHostMiddleware` — guard against Host header attacks
- `GZipMiddleware` — compress responses > 500B
- `HTTPSRedirectMiddleware` — production only

## Validation (Post-Hook)

`check-backend-middleware.ts` verifies the required middleware exists in
`main.py` and follows the patterns above.

## Host Allowlist

`TrustedHostMiddleware` is the outermost guard after CORS and takes its list from
`settings.allowed_hosts` — never a literal. A poisoned `Host` header otherwise
ends up in generated absolute URLs (password reset, redirects), pointing users at
someone else's domain.

`allowed_hosts` is **required** in settings: an allowlist that defaults to
"anything" is the vulnerability it exists to close, so a missing value stops
startup instead of opening the app. An empty list is rejected too — it accepts
nothing, which is a misconfiguration, not a policy.

## Never Do These

- Log with `print()` — use structlog
- Add CORS without `allow_origins` from settings
- Skip the `X-Request-ID` response header
- Add cookie-backed authentication without session-bound CSRF tokens
- Treat `CORS_ORIGINS = ["*"]` as a trusted CSRF origin
