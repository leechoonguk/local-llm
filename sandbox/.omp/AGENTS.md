# FastAPI Standard — Project Guide

## Overview

FastAPI + SQLAlchemy 2.0 (async) + Alembic + Pydantic 2 + APScheduler.
Backend in `backend/`, frontend in `frontend/` (Vite + React + TypeScript).
Python ≥ 3.13, uv for dependency management.

## Project Structure

```
backend/
  app/
    models/         SQLAlchemy ORM models (Base, AuditMixin, domain models)
    schemas/        Pydantic schemas (Create, Read, Update, Internal variants)
    repositories/   Async CRUD repositories (session-scoped)
    services/       Thin service layer (business logic adapter)
    routers/        FastAPI APIRouter endpoints (RESTful CRUD)
    dependencies/   DI wiring (core, services)
    core/           Settings, database engine
    batch/          Scheduled background jobs (APScheduler)
    tests/          pytest + httpx TestClient
  alembic/          DB migrations
  scripts/          start.sh
  Makefile
  pyproject.toml
frontend/
  src/              React + TypeScript
  vite.config.ts
decks/
  Makefile          Build all decks to HTML (Marp)
  <deck>/           One directory per deck (slides.md source)
.omp/              rules/ hooks/
```

## Rules (`.omp/rules/`)

Domain rules live in `.omp/rules/` and are **never** imported here. There are
exactly three delivery channels, and only one of them puts a rule body in front
of the model on its own:

| Channel | Frontmatter | What actually reaches the model |
|---|---|---|
| Rulebook | `description` + `globs` | Only the line `- <name> (<globs>): <description>`. The body is read on demand via `rule://<name>` |
| Always-apply | `alwaysApply: true` | Full body in every session's system prompt — capped at 2 rules by `check-omp-rules` |
| TTSR trigger | `condition` (regex) + `scope` + `interruptMode` | Full body injected the moment a matching stream appears — an edit is aborted before it lands |

**`globs` do not deliver anything.** Editing a file that matches a rule's globs
injects nothing: measured, and stated in the harness docs (`globs` "is not used
to automatically select rulebook rules"). On a TTSR rule, `globs` is only a path
gate. So a rulebook rule is documentation of an invariant that a hook enforces
mechanically — the enforcement is the hook (`make verify`), never the listing.

`RULES.md` (this directory, not `rules/`) is the sticky always-apply rule.

Naming: `<scope>-<name>.md` (e.g. `backend-domain.md`). Adding a rule = creating
the file only; no `@rules/` entry here. A TTSR trigger additionally needs a row
in the `omp-hooks.md` mapping table pointing at the hook that owns the invariant,
and `omp ttsr test` proof that it fires on the construct and stays quiet on prose.

## Development Workflow

Before applying or modifying any code pattern for the first time, use **Context7** (`context7-mcp`) to look up relevant library/framework documentation. Query the library ID, fetch the current docs, and apply patterns based on verified content — not assumptions. This applies to backend (FastAPI, SQLAlchemy, Alembic, Pydantic, APScheduler) and frontend (Vite, React, TypeScript) libraries.
