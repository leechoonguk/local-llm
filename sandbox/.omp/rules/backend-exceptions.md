---
description: Backend exceptions — every raise is a core exception from app/core/exceptions.py, mapped by one handler layer
globs:
      - backend/app/core/exceptions.py
      - backend/app/services/*.py
      - backend/app/routers/*.py
      - backend/app/dependencies/*.py
      - backend/app/core/*.py
alwaysApply: false
---

# Backend Exceptions

A failure has one vocabulary and one translator. **Every `raise` in
`backend/app/` names a class defined in `app/core/exceptions.py`**, and
`setup_exception_handler` is the only place that turns it into a status code and
a response body.

The alternative — each layer inventing its own failure type — means the same
condition answers 404 in one path, 500 in another, and a stack trace in a third.
The client cannot branch on any of it.

Machine-checked by `check-backend-exceptions.ts`:
`ast-grep/rules/exceptions/` owns the shape of a raise; `lib/backend-exceptions.ts`
owns what needs two files at once (definition, handler, response body).

## The Rules

| # | Rule | Why | Owner |
|---|---|---|---|
| 1 | Raise only classes defined in `app/core/exceptions.py` | one vocabulary, one handler layer | `lib/backend-exceptions.ts` |
| 2 | No builtin raise (`ValueError`, `RuntimeError`, `Exception`, `KeyError`, `TypeError`, `AssertionError`, `NotImplementedError`) | no handler → 500 + stack trace | `exceptions/builtin-forbidden.yml` |
| 3 | No `HTTPException` anywhere — not even constructed | a status at the raise site is a second translator | `exceptions/http-exception-forbidden.yml` |
| 4 | Name the class at the raise site, never `raise stored_instance` | the reader (and the checker) must see which failure this is | `exceptions/instance-raise.yml` |
| 5 | Every core class has exactly one `@app.exception_handler` (a subclass may rely on its parent's) | an unhandled core exception is a 500 | `lib/backend-exceptions.ts` |
| 6 | Every handler maps a class that exists here, or a declared third-party one | a handler for a deleted class is dead code | `lib/backend-exceptions.ts` |
| 7 | Every handler returns `detail`, `code`, `request_id` and an explicit `status_code` | clients branch on `code`; support needs `request_id` | `lib/backend-exceptions.ts` |
| 8 | Class names end in `Error` | the suffix is what marks a class raisable | `lib/backend-exceptions.ts` |
| 9 | The `code` is the contract; `detail` is diagnostic. A failure a client must tell apart carries its **own** `code`, never a different `detail` under a shared one | the UI shows a translated sentence keyed by `code` — it never renders `detail` | `lib/backend-exceptions.ts` + `check-frontend-i18n.ts` |

## Codes Are the Contract

`detail` is English written for a log line and a support ticket. It is not the
string a user reads, because the app is bilingual and the server does not know
which language the caller wants. So the client maps `code` to a translated
message, and the code set is the published vocabulary of failures.

That has one consequence worth stating: **two causes a user must distinguish
need two codes.** `IntegrationConfigurationError` used to answer every
configuration mistake with `integration_configuration_invalid`, so a taken
provider code, a non-HTTPS base URL, and a malformed operation path were one
code with three English sentences. A client could not tell them apart without
parsing prose, and the form could not point at the field that was wrong.

```python
raise IntegrationConfigurationError(
    "Provider code must use lowercase letters, digits, and hyphens",
    code="provider_code_invalid",
)
```

The handler emits `exc.code`, and `check-frontend-i18n` fails when a code has no
`errors.<code>` entry in every locale — so publishing a new failure mode without
a translation is a gate failure, not a screen that shows `unknown_error`.

## The Two Documented Exemptions

- **Pydantic validators raise `ValueError`.** `@field_validator` /
  `@model_validator` bodies must, by framework contract: Pydantic converts it
  into a `ValidationError` → 422. The AST rule scopes the exemption to
  validator-decorated functions, so a `ValueError` anywhere else still fails.
- **Third-party classes in the handler allowlist.** `StaleDataError` is raised by
  SQLAlchemy's optimistic lock (`version_id_col`), so it cannot be a core class;
  it is mapped on purpose and declared in `EXTERNAL_HANDLED` with its reason.
  Anything else registered as a handler must be defined in core.

## Layer Responsibilities

```text
repository  → returns None / raises nothing (no policy)
service     → raises the core exception that names the failure
router      → raises nothing; the handler layer answers
dependency  → raises the core exception (AuthenticationError), never HTTPException
core/*      → raises the core exception of its own domain (IntegrationError, …)
handlers    → the only place a status code appears
```

## Adding a Failure Mode

1. Define the class in `app/core/exceptions.py`, named `<Thing>Error`, carrying
   the data its response needs (`resource_id`, `detail`, `provider`).
2. Register one handler in `setup_exception_handler` with an explicit
   `status_code` and the uniform body (`detail`, `code`, `request_id`).
3. Raise it from the layer that detects the condition.
4. Run `make check-backend-exceptions` — the class↔handler sync is bidirectional,
   so a class without a handler (or the reverse) fails.

## Never Do These

- Raise a builtin exception outside a Pydantic validator
- Raise or construct `HTTPException` in app code
- `raise` a stored exception instance by variable name
- Define an exception class outside `app/core/exceptions.py`
- Leave a core exception without a handler, or a handler without its class
- Return an error body without `code` / `request_id`, or without an explicit status
- Map a third-party exception without declaring it in the allowlist and here
