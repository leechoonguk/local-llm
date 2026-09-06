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

- **Ruff**: `E`, `W`, `F`, `I`, `UP`, `B`, `SIM`, `D` (tests only), and the
  complexity three — `C901`, `PLR0912`, `PLR0915`
- Run: `make lint` (ruff check app alembic tests)

### Complexity

Measured by the linter that already runs, at ruff's defaults: cyclomatic 10,
branches 12, statements 50. This is the answer to "should we add SonarQube":
complexity was the one thing Sonar offered that nothing here measured, and it
costs three rule names instead of a server, a token and a CI pipeline the
repository does not have. Coverage (100%), types, dead code and formatting are
already stricter here than a default quality gate.

**Two rules are deliberately absent.** `PLR0913` (arguments) would fight
`backend-router-params.md` on every endpoint — a router's signature is its
contract with FastAPI's DI and with OpenAPI, so eight parameters there is the
standard, not a smell. `PLR0911` (returns) would push guard clauses into nested
tails.

### Security (`S`)

Bandit's rules, on the same terms — and they paid for themselves on the first
run. `S314` found the provider XML decoder parsing attacker-controlled bodies
with the stdlib parser: measured on this Python, `xml.etree` expands internal
entities (three levels of the classic nesting turned three tokens into 300
characters, exponential in the depth a provider picks), so a compromised
provider could answer with a body that expands to gigabytes inside the process.
External `SYSTEM` entities were already refused, so a file read was never the
exposure — the memory bomb was. Fixed with `defusedxml`, and the measurement is
now a test (`test_execute_refuses_hostile_xml_entities`).

The rest of `S`'s findings here read a *name*, not a value: `SECRET_FK`,
`SECRET_NAME_TAKEN_CODE`, `token_type`. Those carry a `# noqa: S105` and a line
saying what the constant actually is. Tests are exempt from the fixture-shaped
rules (`S101`, `S105`, `S106`, `S107`, `S314`, `S603`): a test asserts, holds
fixtures that look like credentials, builds the hostile XML it is proving unsafe,
and runs our own migration binary.

**Suppress at the site, with the reason.** Three functions carry `# noqa` today,
and all three are the same species: wide, flat, exhaustive dispatch, not tangled
logic — the exception-handler registry (eleven flat registrations whose literals
two checks read), `IntegrationClient.execute` (one retry frame whose five endings
share the same attempt bookkeeping), and `_serialize` (one branch per wire type).
A file-wide ignore would have exempted every function written there afterwards;
a docstring paragraph beside the `noqa` says why the shape is the right one.

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
