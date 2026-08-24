---
description: Backend file upload — UploadFile, size limit, content-type allowlist
globs:
      - backend/app/routers/*.py
alwaysApply: false
---

# Backend File Upload

## Purpose

Safe file uploads.

## Standard

- `UploadFile`; `max_size` from settings; content-type allowlist
- Store to disk/object storage; never inline in DB

## Validation (Post-Hook)

`check-backend-file-upload.ts` verifies upload guards when present.


## Dormant Until the Feature Exists

No endpoint accepts an `UploadFile` today, so `check-backend-file-upload` reports
`dormant` and the AST rule matches nothing. That is the intended state: the
standard is written before the feature, and the check wakes with the first
`UploadFile` parameter. "Never store a file inline in the database" has no
syntactic form and stays a review concern.

## Never Do These

- Accept uploads without a size limit
- Store files inline in the DB
