---
description: Backend audit log — created_by/updated_by query API
globs:
      - backend/app/routers/audit.py
alwaysApply: false
---

# Backend Audit Log

## Purpose

Expose AuditMixin fields (created_by/updated_by/timestamps) via a read-only API.

## Standard

- `GET /api/v1/audit` listing resources with `created_by`/`updated_by`/timestamps
- Read-only; admin or owner scoped
- Never exposes hashed_password or internal fields

## Validation (Post-Hook)

`check-backend-audit-log.ts` verifies the audit endpoint when present.

## Read-Only Surface

The audit trail answers "who changed this row". A write endpoint on that surface
lets the record of a change be changed, which makes every answer unfalsifiable -
so `ast-grep/rules/audit-readonly/write-endpoint.yml` allows `@router.get` only, and
runs as soon as `app/routers/audit.py` exists.

## Never Do These

- Expose internal fields (hashed_password) in audit responses
- Allow writes through the audit endpoint
