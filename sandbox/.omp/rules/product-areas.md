---
description: Product areas — the navigation's three areas each carry one screen pattern, and every domain in an area carries that pattern's legs
globs:
      - frontend/src/layouts/dashboard/config-navigation.tsx
      - frontend/src/sections/**/*.tsx
      - frontend/src/lib/api/endpoints.ts
      - frontend/src/lib/api/hooks/*.ts
      - backend/app/routers/*.py
      - .omp/hooks/lib/hook-product-areas.ts
alwaysApply: false
---

# Product Areas

## Why An Area, And Not Just A Screen Type

`frontend-screens.md` classifies a screen by its **file**: a `*List.tsx` is a
list, a `*DerivedList.tsx` is read-only, a `*FormDialog.tsx` is a form. That
answers "is this file built like its kind" and cannot answer "is this domain
built like the thing it *is*".

Measured on this repository: `IntegrationList` and `BatchList` are the same
archetype — a configuration row whose real work happens elsewhere — and every
file-level check passed while the integration domain was missing the archetype's
third leg entirely. `integration_call` is written on every external call
(`IntegrationCallRepository.create`), there was **no endpoint that reads it** and
no screen that shows it, so "what did we send last night" was unanswerable from
the product. Nothing was red, because no check knew the two domains were the
same kind of thing.

So the unit here is the **area**: the navigation's own grouping, which is the
product's statement of what belongs together, paired with one pattern per area.

## The Three Areas

`NAV_GROUPS` in `config-navigation.tsx` is the source of membership — the same
list `check-frontend-routing` already compares against the path registry. Each
group's `subheaderKey` maps to exactly one pattern in
`.omp/hooks/lib/hook-product-areas.ts`:

| Area (nav group) | Pattern | Domains today |
|---|---|---|
| `group.user` (사용자) | **record** — the row *is* the record | `user` |
| `group.batch` (배치) | **operations** — the row is configuration; the work is elsewhere | `batch`, `integration` |
| `group.food` (식품) | **derived** — nothing is written from this side | `food_*` |

A group whose `subheaderKey` has no declared pattern fails the check: an area
nobody assigned a pattern to is an area whose screens answer to nothing.
`dashboard` is its own screen type (`frontend-screens.md`, Dashboard) and sits in
the ungrouped head of the navigation; a nav item whose section directory has no
list screen — the food chat — is exempt for the same reason.

## Pattern: record (사용자)

The record is the row, so:

- every field of `<Domain>CreateRequest` is an `editable: true` column and `+`
  opens a draft row (owned by `check-frontend-domain`);
- there is **no** `<Domain>FormDialog.tsx` — a dialog would ask for what the row
  already holds;
- the row is not a door: a row that opens a record when clicked cannot also be
  the row that record is typed into.

## Pattern: operations (배치, 외부 연동)

A configuration row whose effect is elsewhere. Three legs, and the third is the
one that was missing:

1. **The configuration** — a list whose scalars are edited in the row
   (`editable: true`), and a create dialog, because an identity chosen once
   (`code`) cannot be a cell the server would ignore.
2. **An exercise verb** — a `POST` on the row that makes it happen now:
   `POST /batch/{batch_id}/run`,
   `POST /integration/{integration_id}/operations/{operation_code}/execute`.
   A configuration nobody can try is a configuration nobody can trust.
3. **An execution log** — a `GET` that reads what the exercises did, and a
   read-only surface that shows it, **entered from the row**:
   `GET /batch/{batch_id}/runs` → `BatchRunsDialog`,
   `GET /integration/{integration_id}/calls` → the detail dialog's calls tab.
   The log's child collection per domain is declared in
   `lib/hook-product-areas.ts` (`EXECUTION_LOG`), because the word differs by domain
   (`runs`, `calls`) while the leg does not.

The row is the door to that log surface, and the area therefore carries **no
view/history button**: one intent, one control (`frontend-screens.md`, the door
and its guards).

## Pattern: derived (식품)

Every list in the area is a `*DerivedList.tsx`: the rows are rebuilt nightly
from the ledgers, so this side reads them and writes nothing. The forbidden
half — mutations, form dialogs, row actions — is owned by
`check-frontend-screens`; what this check adds is that a **food list may not be
a plain `*List.tsx`**, which is how a writable screen would appear in a read-only
area without any file looking wrong.

## Adding A Domain

1. Put it in a nav group — that is the area, and the area is the pattern.
2. Carry that pattern's legs. For `operations`, declare its log collection in
   `EXECUTION_LOG` in the same change; a domain in the area with no declared log
   fails, because the third leg is exactly what a file-level check cannot see.
3. Run `make check-product-areas`.

## Never Do These

- Add a nav group without mapping its `subheaderKey` to a pattern.
- Put an operations domain in the navigation with no exercise verb or no log
  read — the configuration then has no evidence it ever ran.
- Keep a view/history button beside a row that is already the door to the same
  surface.
- Give a food screen a writable list file.
