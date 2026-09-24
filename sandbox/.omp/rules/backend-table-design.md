---
description: Backend table design — atomicity (1NF), keys, constraints, audit trail for SQLAlchemy models
globs:
      - backend/app/models/*.py
alwaysApply: false
---

# Backend Table Design

## Scope

Every SQLAlchemy model in `backend/app/models/` is a table design decision.
This rule fixes the invariants that a reviewer would otherwise have to check by
hand, and that a schema is expensive to fix once data exists.

Domain layering (5-layer CRUD, repository/service split) stays in
`backend-domain.md`. Migration mechanics stay in `backend-migrations.md`.

## Atomicity (1NF)

A column holds **one** value of **one** meaning.

- **No numbered repeating groups.** `phone1`/`phone2`, `amt_1`/`amt_2` are a
  child table wearing a disguise: they cap cardinality, force `COALESCE` chains,
  and make "how many are set?" unanswerable in SQL. Model the repetition as rows.
- **No delimiter-packed columns.** A `String` holding `"a,b,c"` cannot be
  indexed, joined, or constrained per element. Use a child table, or `JSON` when
  the payload is genuinely opaque to the database (external API bodies, schemas).
- A `JSON` column is a deliberate escape hatch for opaque documents — never a
  shortcut around modelling a relationship the application queries by.

## Keys and References

- Every table declares a primary key. UUID PKs use `Uuid` + `default=uuid4`.
- Foreign key columns are named `<referenced_table>_id`.
- Every `ForeignKey` declares `ondelete=` explicitly. Leaving it to the default
  turns a parent delete into either a surprise error or a silent orphan.
- Every foreign key column carries `index=True`. An unindexed FK makes every
  join and every cascade a full scan.
- Cascade intent lives in one place per relationship: `ondelete=` on the
  constraint plus `passive_deletes=True` on the relationship, so the database
  performs the cascade rather than the ORM loading children to delete them.

## Closed Value Sets

A short bounded `String` naming a type, status, mode, format, source, kind, or
direction is a closed set. Constrain it in the database:

```python
value_type: Mapped[str] = mapped_column(String(20))
# __table_args__
CheckConstraint(
    "value_type IN ('STRING', 'INTEGER', 'NUMBER', 'BOOLEAN', 'DATE', 'DATETIME', 'JSON')",
    name="ck_<table>_value_type",
)
```

Without the constraint the column accepts `'BANANA'`, and the invalid row
outlives the release that wrote it. Free-form media/content strings
(`request_media_type`, length > 32) are not closed sets and are exempt.

## Column Types and Bounds

- **Every `String` column declares an explicit length.** A bare `String` is an
  unbounded `varchar`: the database enforces no input contract, and the column
  stops documenting what it is meant to hold. Established lengths in this
  codebase: identifiers/codes `50`–`64`, display names `120`, descriptions
  `512`, URLs/pointers `2048`.
- **Booleans are `NOT NULL`.** `Mapped[bool | None]` is three-state logic that
  every reader must interpret; give it a default or split the unknown case into
  its own column.
- **Timestamps are timezone-aware.** `DateTime(timezone=True)` only. A naive
  timestamp silently means "server local time", which changes with deployment.

## Concurrency

`AuditMixin` carries a `version` counter wired as SQLAlchemy's
`version_id_col`, so every `UPDATE` is qualified by the version it read:

```python
@declared_attr.directive
def __mapper_args__(cls) -> dict[str, Any]:
    return {"version_id_col": cls.version}
```

Two requests that load the same row concurrently no longer both win — the
slower commit matches zero rows and raises `StaleDataError`, which
`setup_exception_handler` maps to **409** with code `stale_version`. Without
it, the second write silently discards the first one's columns.

`version` is part of every Read response so a client can observe which
revision it holds (`check-backend-domain`, every `*ReadResponse` in every
layout), and `StaleDataError` must have its handler (`check-backend-exceptions`)
- deleting it turned every concurrent write into a stack-traced 500 while every
gate stayed green, measured.

**Every `AuditMixin` table carries the lock, including the ones that do not need
it - and that is the criterion, not an oversight.** Where a second writer
exists the lock is load-bearing: two admins on one `user` form, the job
finishing a `batch_run` while the UI stops it, a scheduled and a manual run
storing one `batch_checkpoint`, a refresh token rotated and revoked at once.
Where there is one writer (`food_*` ledgers, written over whole every night) it
is constant - `max(version) = 1` always, since no row is ever updated - and where a table is
append-only (`integration_call`) it is inert. The alternative, a second mixin
for tables that opt out, creates a decision on every new table, and that
decision fails in one direction only: a table that gains an editor later and
lacks the lock loses updates silently, and no check can see a lock that is
absent. An integer column and one `WHERE version =` clause is the price of
never making that decision.

## Audit Trail

Every table model inherits `AuditMixin` (`created_by`, `updated_by`,
`created_at`, `updated_at`, `version`). Audit columns are the cheapest
incident-response tool available and cannot be backfilled after the fact.
`created_by`/`updated_by` store the acting **username** (`String(50)`), not a
user foreign key: an audit trail must survive the deletion of its actor.

## Naming

- `__tablename__` is required, lower snake case, and **singular**
  (`integration_request_field`, not `integration_request_fields`).
- A ledger — one portal operation's copy, written over nightly — says so in its
  name: `<domain>_ledger_<feed>` (`food_ledger_nutrition`). The bare `<domain>_*`
  names belong to the tables a router speaks (`rule://backend-relations`).
- Constraint names carry their kind and table: `uq_<table>_<cols>`,
  `ck_<table>_<subject>`, `ix_<table>_<cols>`. Unnamed constraints get
  database-generated names that migrations cannot reference. PostgreSQL truncates
  an identifier at 63 characters **silently**, so a derived name that would exceed
  it is replaced by a shorter explicit one, with the count in a comment beside it
  (`ix_food_ledger_livestock_raw_material_item_report_no`, 64 before shortening).

## Validation (Post-Hook)

`check-backend-table-design.ts` validates, per mapped class **and per
column-bearing mixin** (a mixin's columns land in every table that inherits it,
so skipping mixins would exempt `AuditMixin` from every rule below):

1. `__tablename__` present, lower snake case, singular
2. Primary key declared
3. `AuditMixin` inherited
4. No numbered repeating-group columns (1NF)
5. Booleans not nullable
6. `DateTime` columns are `timezone=True`
7. Foreign keys: `_id` suffix, explicit `ondelete=`, `index=True`
8. `String` columns declare an explicit length
9. Closed-value-set columns (`*_type`/`*_status`/`*_mode`/`*_format`/`*_source`/
   `*_kind`/`*_direction`, `String(≤32)`) carry an `IN (...)` check constraint
10. `AuditMixin` defines `created_by`, `updated_by`, `created_at`, `updated_at`,
    `version`, and sets `version_id_col` — a `version` column without the mapper
    argument is decoration, and concurrent writes silently overwrite
11. A named constraint starts with `<kind>_<table>_`, unless the full name would
    pass 63 characters (`ix_food_ledger_livestock_raw_material_item_report_no`)

Related machine checks elsewhere:

- `check-backend-domain.ts` — every Read response exposes `version: int`, and a
  service never assigns `updated_at` (the repository sets it before its flush;
  a post-flush assignment costs a second `UPDATE` and a second version bump).
- `check-backend-integration-configuration.ts` — the same `version` requirement
  for the integration Read classes.
- `check-backend-migrations.ts` — a revision that renames a table renames its
  primary key with it. PostgreSQL leaves the pkey under the old table's name and
  `alembic check` never compares pkey names, so the drift is invisible to every
  other gate: measured here, eleven renamed ledgers kept `food_<old>_pkey` and
  the next table to take one of those names was created as `..._pkey1`.

## Never Do These

- Add a numbered column when the answer is a child table
- Pack multiple values into one `String` with a delimiter
- Declare a `ForeignKey` without `ondelete=` or without `index=True`
- Leave a short type/status/mode string unconstrained
- Use a nullable `Boolean`, a naive `DateTime`, or an unbounded `String`
- Skip `AuditMixin` on a table model
- Pluralize `__tablename__`
- Rename a table and leave its primary key under the old table's name
- Name a constraint after a table it does not belong to
