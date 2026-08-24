---
description: Backend code conventions — Python version, linter config, Pydantic, SQLAlchemy, testing
globs:
      - backend/pyproject.toml
      - backend/app/**/*.py
      - backend/alembic/**/*.py
alwaysApply: false
---

# Backend Code Conventions

## Python

- **Python ≥ 3.13**, `target-version = "py313"`, `line-length = 100`
- `from __future__ import annotations` in all generated files (static analysis compat)

## Linting

- **Ruff**: `E`, `F`, `I`, `UP`, `B`, `SIM` rules
- Run: `make lint` (ruff check app alembic)

## Type Checking

- **Pyright**: `typeCheckingMode = "standard"`
- Run: `make typecheck` (pyright)

## Testing

- Tests use **in-memory SQLite** + `TestClient`
- DI override for `get_session` in `conftest.py`

## Layer-Specific Conventions

Pydantic/SQLAlchemy/UUID conventions per layer are documented in
`backend-domain.md` — that rule is the single source for the 5-layer pattern.
This rule covers tooling configuration only.
