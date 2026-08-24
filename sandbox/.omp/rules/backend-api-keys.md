---
description: Backend API keys — service accounts, X-API-Key header
globs:
      - backend/app/dependencies/api_key.py
alwaysApply: false
---

# Backend API Keys

## Purpose

Machine-to-machine auth via API keys, distinct from user JWT.

## Standard

- `ServiceAccount` model; `X-API-Key` header; `get_api_key` dependency
- Distinct from user JWT; scoped permissions

## Validation (Post-Hook)

`check-backend-api-keys.ts` verifies the API key dependency when present.

## Never Do These

- Reuse the user JWT for service accounts
- Log the API key value
