---
description: Frontend ↔ backend contract — TS types mirror Pydantic schemas, endpoints mirror routers
globs:
      - frontend/src/types/*.ts
      - frontend/src/lib/api/endpoints.ts
      - backend/app/schemas/*.py
      - backend/app/routers/*.py
alwaysApply: false
---

# Frontend Contract

The frontend's types and endpoint table are a hand-written copy of the backend's
schemas and routers, and a copy drifts in silence. A field renamed on the server
still compiles on the client and arrives `undefined`; a renamed router prefix is
a 404 nobody sees until someone opens the screen. TypeScript cannot catch either,
because the wire is `any` until someone declares otherwise.

Machine-checked by `check-frontend-contract.ts` (`make check-frontend-contract`),
which parses both sides and compares them in both directions.

## What Is Compared

| Backend | Frontend | Rule |
|---|---|---|
| `<Domain>ReadResponse` fields | `interface <Domain>` (with inherited fields) | equal sets, both ways |
| `AuditMixin` + primary key | `AuditedResource` | `id`, `created_by`, `updated_by`, `created_at`, `updated_at`, `version` |
| error body in `app/core/exceptions.py` | `ApiErrorBody` | `detail`, `code`, `request_id` |
| every `@router.<verb>("<path>")` in **any** router module | the call a service issues | equal (verb, path) sets, both ways; a route with no caller must be declared with its reason |
| every entry of `<DOMAIN>_ENDPOINTS` | a service function that uses it | no declared-and-never-called constant |
| `Field(min_length=…, max_length=…, pattern=…)` on `<Domain>CreateRequest` | the `yup` chain in `<Domain>FormDialog` | same numbers; no client-only pattern |
| every request model, nested ones included | the TS interface of the same name | equal field sets, both ways — the backend is the canonical shape |
| every field's annotation | the TS type beside it | `str`/`UUID`/`datetime` → `string`, `int`/`float` → `number`, `bool` → `boolean`, `list[X]` → `X[]`, `dict[...]`/`JsonObject` → `Record<string, unknown>`, `object` → `unknown`, `Literal[...]` → the same union, `<X>ReadResponse` → `X` |
| `X \| None` in a response | `T \| null` | required key, nullable value |
| a request field with a default | `field?: T` | omitted means "leave it alone" |
| `@router.<verb>` + path | the verb the service calls | equal (verb, path) pairs |
| `Annotated[int, Query(...)]` parameter | a field of a params type | every router query parameter is declarable |
| the handler return annotation | the generic a service passes | `list[<X>ReadResponse]` -> `X[]`, `dict[str, bool]` -> `OkResponse`, `<X>ReadResponse` -> `X` |
| `OAuth2PasswordRequestForm` / `Form(...)` | the body a service sends | form-encoded both sides, or neither |
| path parameters in the route | arguments the endpoint constant takes | equal counts |
| `Query(ge=, le=)` | `PAGE_SIZE_OPTIONS` / `DEFAULT_PAGE_SIZE` / `MAX_PAGE_SIZE` | every value the UI can send is inside the bounds |

A path parameter's name is not part of the comparison: `/user/{user_id}` and
`` `/user/${id}` `` both normalise to `/user/{}`, because the two sides name the
same parameter differently on purpose.

## Nobody Owns Half an Endpoint

An endpoint can exist on exactly one side and nothing notices, because the two
halves are written by hand against each other. Both directions were measured
here, on this repository:

- **Backend-only** — the API creates and deletes integration secrets, and no
  screen does. That is a feature half-built or an endpoint that should not be
  published; either way it is a decision, not something to rediscover in the
  router months later.
- **Dead constant** — `INTEGRATION_ENDPOINTS.DELETE_SECRET` was declared and
  never called: exactly what a half-built feature leaves behind. Deleted.
- **Frontend-only** — a call the server does not route answers 404 or 405 in the
  browser, for the user, with no build error anywhere.

**Coverage is measured from the screen, not the transport.** A route counts as
called only when a screen can reach it: service function → query hook → screen.
Stopping at the service layer is why this passed while the app had no operation
feature at all — `integrationService.execute` and `useExecuteOperation` existed
and nothing rendered them, and `listSecrets` had no hook. `listSecrets` is gone;
the execute chain now ends in a screen (`IntegrationRunPanel`), so the route
is covered by a caller rather than by an exemption.

A route reachable only by an orchestrator or an operator belongs in
`NOT_FROM_BROWSER` **with its reason** (`check-frontend-contract.ts`). The list
is checked in both directions too: an exemption whose route no longer exists
fails, so it cannot rot into a blanket allowance.

## Validation Is Part of the Contract

A form rule and a server rule are the same rule written twice, and each way of
disagreeing is a bug that was measured in this repository:

- **Client-only rule** — the user dialog required an email shape and an 8-char
  password while `UserCreateRequest` said `str`. `curl` created a user with the
  email `not-an-email` and the password `x`, and the API answered **201**. A
  rule the browser enforces alone is a rule every other client ignores.
- **Invented rule** — the integration dialog demanded `^[a-z][a-z0-9_]*$` for
  `code`, which rejects `mfds-food-safety-korea`: the provider the app itself
  seeds. The server only capped the length, so the form blocked input the API
  accepts.
- **Stale rule** — the server tightens `max_length` and the form keeps the old
  number, so the user gets a generic 422 toast that names no field.

So the length lives in one named constant per side, and
`check-frontend-contract` compares them. A `.matches()` in a dialog requires a
`pattern=` on the server field; otherwise the check fails and the choice is
explicit: declare it on both sides or drop it.

**Required is the third axis, and it runs both ways.** A field the server has no
default for must carry `.required()`, or an empty submit comes back a 422 naming
no field; a field the server defaults must not, or the form refuses a body the
API accepts. A boolean is exempt by construction — a checkbox always submits a
value, so yup spells its state `.defined()` and "required" means nothing there.

**The check was applying to one domain out of three.** `readBackendModule` looked
for `schemas/<domain>.py`, and `batch` and `integration` had long since become
folders (`schemas/batch/{schedule,run,step,checkpoint}.py`), so the lookup
returned null and `checkValidationParity` returned early — silently, while
reporting PASS. A folder domain now reads as the concatenation of its modules,
which is what `readLayerSource` already does for the backend structure checks.
This is the harness's one failure mode that leaves no trace: the check did not
break, it stopped applying.

### The panel is a form too

The rules above read `<Domain>FormDialog.tsx`, and the three dialogs in this app
hold only strings and booleans. **Every numeric bound the backend declares lives
on a nested record** — timeouts, retry counts, an ordinal — edited through a
panel that check never opened. Measured on `IntegrationOperationPanel`:

| Field | Server | Control declared |
|---|---|---|
| `path_template` | `max_length=2048` | nothing |
| `response_root` | `max_length=512` | nothing |
| `connect_timeout_ms` | `gt=0` | nothing |
| `read_timeout_ms` | `gt=0` | nothing |

So a panel control declares the bound its field's schema declares:
`ScalarField` carries `maxLength`, `NumberField` carries `min`/`max`. The schema
is found by the naming the record-dialog standard already uses — `<Name>Panel.tsx`
↔ `<Name>CreateRequest` — so a panel that edits no record (`IntegrationRunPanel`
is a console) is skipped rather than guessed at, and a field the panel does not
render is never demanded.

**Only bounds the control can actually violate.** `NumberField` strips
non-digits, so a negative cannot be produced and `ge=0` needs no restating.
`gt=0` is the opposite case: `0` is exactly what the widget hands back for an
emptied input, so that field needs its own floor or the user meets the rule as a
422 with no field named.

### Only what crosses the wire

The comparison covers the models an endpoint actually takes or sends. Roots are
what the routers name — the body (`data: <X>Request`) and the return annotation
(`Page[X]` unwrapped) — and the closure follows field annotations, so a nested
`IntegrationOperationCreateRequest` arriving inside a provider `PUT` stays in.

`backend-domain` requires a full schema set per table, so `batch_run`,
`batch_step` and `batch_checkpoint` each have Create/Update/Read classes. The
browser never posts a run, and no endpoint returns a checkpoint at all —
demanding TypeScript twins for those asks the client to declare shapes the API
neither accepts nor answers with.

## Writing the Types

```ts
export interface User extends AuditedResource {
  username: string
  email: string
}
```

- The read model extends `AuditedResource` — never re-declare the audit columns.
- A `Literal[...]` union on the server becomes a TS union of the same members,
  so an unknown value is a compile error rather than a 422 at runtime.
- A nullable column is `T | null`, not `T | undefined`: the server sends `null`.
- An optional request field is `field?: T` — omitted means "leave it alone".

## When the Backend Changes

1. Change the Pydantic schema or the router
2. Run `make check-frontend-contract` (names and paths) and
   `make check-frontend-types` (types, nullability, optionality, verbs) — each
   names the field that no longer matches
3. Update `types/<domain>.ts` and `endpoints.ts`
4. Update the screen that reads the field

## Review Judgement (not machine-checked)

**The backend is the canonical shape.** Which fields exist, which are optional,
and whether a `dict[str, object]` stays a `Record<string, unknown>` are not
review questions: the client mirrors the server exactly, and every later drift —
from either side — fails the gate. A client type that is *stricter* than the
server is the invented-rule bug in another costume.

What is left for a reader:

- Whether the server's own shape is the right shape. The checks make the client
  match it; they cannot say a field should never have existed.
- Whether an annotation the parser cannot read is correct. An unreadable
  annotation is reported, never assumed equal, so the answer is to simplify the
  schema or teach `lib/frontend-types.ts` — not to trust it.

## Never Do These

- Add a response field on the server without adding it to the TS interface
- Declare a TS field the read response never sends
- Re-declare the audit columns in a domain interface
- Type a wire value as `any` to make a mismatch compile
- Build a request URL from a string template outside `endpoints.ts`
- Publish a route no screen calls without declaring why in `NOT_FROM_BROWSER`
- Leave an endpoint constant behind after the feature that used it
- Enforce a length or a character shape in the dialog that the server does not
- Trust a `pattern` nobody measured against the data the app already ships
