---
description: Backend Alembic migration workflow — generate, apply, verify, and model registration rules
condition: "alembic|migrat|downgrade|revision"
scope: "tool:bash"
interruptMode: always
alwaysApply: false
---

<!-- fires-on tool:bash: make migrate-gen m="add notice table" -->

# Migration Rules

## TTSR Activation

This rule is TTSR-triggered: it activates only while a **bash command** matches
`alembic|migrat|downgrade|revision` (`make migrate-gen`, `make migrate`,
`make migrate-down`, `alembic revision …`). It stays dormant otherwise — read it
on demand via `rule://backend-migrations`.

`scope: "tool:bash"` states one stream instead of inheriting prose and every
tool argument. Measured before narrowing: all 17 injections across 87 sessions
fired on descriptive text (`alembic/ # DB migrations`, `check-backend-migrations`)
or on editing a generated revision file, and none on migration work — the
workflow is only actionable at the command, so the command is the only stream
watched. `interruptMode: always` is stated for the same reason: the
machine-global default must not decide whether a migration rule interrupts.

**No `globs` here on purpose**: on a TTSR rule, `globs` is a runtime path gate
that requires file paths in the match context. `bash` tool calls never carry
file paths, so a globbed TTSR rule would never trigger on `make migrate` etc.
See `omp-conventions.md` "TTSR globs trap".

**A run is atomic per migration.** `alembic/env.py` sets
`transaction_per_migration=True`, so a multi-step run that fails stops at the last
revision that fully applied and the version pointer still describes the rows that
are there. `check-backend-migrations` refuses an `env.py` without it.

**A half-applied chain is not a migration defect.** Measured here: a
`downgrade base` that failed part-way left a database whose pointer said 65 while
an operation row from revision 66 was still present, the next `upgrade head` died
on `uq_integration_operation_provider_code`, and half an hour went into diagnosing
an ordering bug that does not exist — the same chain steps down cleanly from a
consistent database, all the way to the first revision. So when a migration error
names a constraint rather than your change:

1. `make db-init` — put the database back where the files say it is;
2. reproduce. If it passes, the defect was the state, not the chain;
3. only then read the migrations, and read them **in revision order**, because a
   downgrade error names the revision it ran, not the one that made it fail.

Never walk the whole chain down on a database you are about to diagnose from:
`make db-init` is the reset (it drops the volume), and it is one command.

## Enforcement

`strict-backend-migrations` blocks edits to pushed revisions before they happen,
and `check-backend-migrations` proves ORM ↔ DB sync plus one-table scope after
every edit. This rule's injection is the workflow knowledge those two hooks
cannot state: which command to run, in what order, and what to check afterwards.

## Model Registration

Every SQLAlchemy model **must** be imported in `alembic/env.py` so it
registers on `Base.metadata` before autogenerate runs:

```python
from app.models.item import Item   # noqa: F401 — register model on metadata
from app.models.batch import Batch   # noqa: F401
```

If a new model is not imported here, `make migrate-gen` will produce an
**empty migration** (no table created). Always check the generated
migration file for `op.create_table(...)`.

## Generate

```bash
make migrate-gen m="add <name> table"
```

- Revision ID is auto-incremented (numeric).
- `m` must be non-empty — the message becomes the filename slug; `make migrate-gen`
  refuses an empty one, and `NN_.py`-style empty-slug files fail `make check-backend-migrations`.
- A generated file whose `upgrade()` is only `pass` means nothing changed — delete
  the revision; an empty upgrade fails the check too.
- Message should be short, imperative: `"add todo table"`, not `"created the todo table for storing todos"`.
- **Always inspect** the generated file in `alembic/versions/` before applying.

## Revision Scope and Immutability

- Revisions `1` through `6` are the pre-policy baseline. They are grandfathered
  from the immutability hook and one-table policy so their historic local
  corrections do not block unrelated work.
- Revision `7` and later remain editable until present on the current Git upstream
  (`@{upstream}`). After push, they are immutable: create a new revision to correct
  them; never rewrite deployed schema history.
- The one-table rule applies to every unpushed revision `7` and later. Split
  changes for multiple tables into separate revisions, including indexes and constraints.
- Unpushed revisions may not use `op.execute` **with raw SQL** (a string, or
  `sa.text(...)`): a SQL string hides its target from the one-table check. A
  statement over a `sa.table(...)` declared in the same revision is allowed —
  it names its table to the same reader `op.bulk_insert` does. Without that
  distinction a seeded row could be inserted but never corrected, which is what
  a renamed job code needs (revision 92).
- `op.bulk_insert` is allowed for seed data, but it must target exactly one table.
- Every unpushed revision—DDL or seed data—must resolve to exactly one table.
- Any revision that creates, alters, drops, or seeds an `integration_*` table must
  include `_integration_` in its filename. The integration checker discovers these
  files automatically; never maintain a hardcoded revision-number list.
- Integration seed tests must discover `*_seed_*_integration_*.py` from the versions
  directory, so a new operation's seed migration cannot be omitted from test setup.
- The integration checker discovers `*_integration_*.py` and operation seed codes
  from the filesystem. Every seeded operation code owns a recorded exchange under
  `tests/core/fixtures/integration/`; hardcoded revision lists are forbidden.

## Seed Filename Convention

```
<revision>_(seed|replace)_<identity>_integration_<table>.py
```

`<identity>` is the row's own name, not its neighbourhood: the **operation** slug
for `operation`/`field` seeds, the **provider** slug for `provider`/`secret`
seeds. A leading `search_` (operation) or vendor prefix such as `mfds_`
(provider) may be dropped — `72_seed_barcode_item_info_integration_operation.py`,
`64_seed_food_safety_korea_integration_provider.py`.

Two things depend on it, one human and one mechanical:

- **A listing is a table of contents.** Measured on this repository: revisions
  66, 70 and 72 seed three *different* operations of one provider and were all
  called `<rev>_seed_food_safety_korea_integration_operation.py`. Nothing in the
  listing said which operation each one carried.
- **Supersession must be unambiguous.** A `_replace_` file supersedes the seed of
  the *same* row and no other. A reader keyed on the filename read those three as
  one lineage and silently kept only the newest, dropping two operations out of
  its own checks — measured while adding the column check. `backend-migration-policy.ts`
  now keys supersession on the seed string, and `listMisnamedSeedFiles()` keeps the
  filename honest for every revision still editable.

Pushed revisions are exempt: they are immutable by policy, and the reader no
longer depends on their names.

`check-backend-migrations.ts` and `strict-backend-migrations.ts` enforce the
same boundary. They permit legacy baseline corrections and local edits to
unpushed revisions, while rejecting changes to an upstream revision `7` or later.

- Immutability is determined solely by whether the revision exists at `@{upstream}`. An
  applied but unpushed revision is still editable. To rerun an edited applied revision,
  downgrade to its parent, then run `make migrate`; never add a corrective revision only
  to bypass a local edit guard.

Immutability is about the **file**, not the tool that reaches it.
`strict-backend-migrations` therefore reads `bash` and `eval` bodies too and
blocks `mv`, `rm`, `cp`, `rename`, `sed -i`, `tee`, `truncate`, `git mv`,
`git rm` and `>` redirects aimed at a pushed revision. Read-only commands are
untouched — naming a migration in `cat`, `grep` or `git log` is how anyone learns
what it did.

Measured: a local model told to follow the seed-filename convention renamed two
**published** revisions with `mv` — the one operation the convention exempts —
and the write/edit guard never saw it, because a rename is not a write. Renaming
a published revision changes what every other checkout has already applied.

## Seed Migration Tests

- Every integration seed revision must have an isolated test that invokes `upgrade()`
  against an empty schema and asserts the seeded provider, operation, and field counts.
- For `SECRET_REF` fields, assert the stored reference and sensitivity flag, never a key
  value. Assert JSON fields constrained by `IS NULL` are persisted as SQL `NULL`.
- Every seeded external operation also needs a mock-transport execution test covering its
  configured path, secret reference, caller inputs, and canonical response mapping.
- `check-backend-integration-configuration` enforces the MFDS seed migration and the
  contract fixture every seeded operation owns.

## Apply

```bash
make migrate          # alembic upgrade head
```

## Schema Is Only Ever Migrated

**Every schema object - a column, a constraint, an index - is declared on the
model and reaches a database through a revision.** Nothing else creates one:
not `psql`, not a script, not application code at runtime.

An index typed into a shell works on the machine it was typed on, is in no
revision, and the next environment is built without it - with the slow plan
and nothing saying why. Measured: the products-of-a-material read
needed `(material_code, report_kind, item_report_no)` on
`food_item_report_ingredient`; the single-column index made the planner spill
its bitmap lossy (seconds a page), and the fix is a
revision generated from the `Index(...)` in the model's `__table_args__`,
never a hand-run `CREATE INDEX`.

Two checks, one per half. `alembic check` sees a database that holds something
the models do not (planted: a hand-made `ix_probe_hand_made` failed at once),
and `check-backend-migrations` refuses DDL inside `backend/app/` - the half no
comparison would ever see, because the statement runs only when that code path
does. `LedgerStage`'s staging table is the one exception: a temporary the pass
creates and drops through SQLAlchemy's `CreateTable`/`DropTable`, never a
string. `ANALYZE` after a whole-table rewrite is not DDL and is required
there - a table rebuilt whole carries statistics for rows it no longer holds.

## ORM ↔ DB Sync Check

`check-backend-migrations.ts` runs `alembic check` (autogenerate diff) on every
tool result and flags drift:

- **ORM drift** (model changed, migration missing) → `New upgrade operations detected`
- **DB drift** (schema changed outside migrations) → also detected
- **DB behind the files** (a written migration was never applied) → **fails** with
  `run 'make -C backend migrate'`. A seed revision that never ran leaves the rows
  its `.http` file and fixture describe absent while every other check passes -
  measured on a local-model integration run that wrote revisions 72 and 73,
  applied neither, and still saw a green gate.
- **DB ahead of the files** (another branch's revision) → dormant, not this tree's problem
- **DB unreachable** (infra down) → skipped silently — never blocks offline work

Fix drift with `make migrate-gen m="..."` then `make migrate`. Run
`make check-backend-migrations` to verify sync on demand.

## A Mixin Column Is One Revision

A revision targets exactly one table - unless the column it changes belongs to a
**mixin**, in which case the unit is the mixin and the revision walks every table
carrying it (read off `information_schema`, not listed by hand). `AuditMixin`
puts `created_by`/`updated_by` on 54 tables; widening them one table per revision
is 54 revisions of one decision, and any subset of them applied is a database
where the same actor name fits in one table and not the next. Revision 268 is
that shape, and `check-backend-migrations` recognises it by the mixin's name
plus the `information_schema` read.

Measured before the widening: three jobs renamed after
their ledgers signed their rows `batch:<code>` past the column's
`String(50)`, and each died writing its first call log - before the portal was
called. `check-backend-batch` now compares every job code against the column
that stores it.

## A Server Default Is Part Of The Schema

`alembic check` compares server defaults only when `env.py` asks it to, and it
did not. Measured: three ledger revisions wrote a `version` column
`nullable=False` with no `server_default`,
every gate stayed green for weeks, and the first pass to fill one of them walked
its whole feed (hundreds of windows, no refusal) and then died
replacing the ledger on the NOT NULL constraint.

`compare_server_default` is on from that day. It is a callable rather than
`True` for one type: the comparison asks the database `SELECT <inspected> =
<rendered>`, and for a JSON column that is `'{}'::json = '{}'`, which Postgres
has no operator for - so a JSON default reads as unchanged and every other
column is compared.

## A CHECK Body Is Invisible To Alembic

`alembic check` compares tables, columns, indexes and a constraint's
**presence** — never the set inside a `CHECK (col IN (...))`. Measured:
`SKIPPED` was added to `batch_run.status` in the model, the schema
`Literal` and the TypeScript union, no revision touched `ck_batch_run_status`,
and every gate passed. The first run that ended SKIPPED was refused by the
database, its ending was never written, and two derive runs sat RUNNING for
ever — which the next fire then read as "a derivation is already running" and
stood down from.

So a changed vocabulary is a revision of its own, `drop_constraint` +
`create_check_constraint` over the one table, and two readers watch it:

- `check-backend-migrations` fails when a model's `CheckConstraint` set differs
  from the upstream revision of that file and no unpushed revision names the
  constraint.
- `check-backend-domain` compares every model `CheckConstraint` with
  `pg_constraint` in the running database, and reports `DORMANT` rather than a
  pass when it cannot reach one.

## Rollback

```bash
make migrate-down     # alembic downgrade -1
```

Test rollback after every new migration to verify `downgrade()` is correct.

## Revision File Layout

A revision is read years after it ran, usually by someone deciding whether it
can be reverted. The shape is therefore fixed, and `check-backend-migrations`
enforces it on **every revision that is not yet pushed** — a pushed revision is
immutable, so the layout standard binds the ones still being written.

- **Docstring** — the summary line names the change, and the generated
  `Revision ID:` / `Revises:` header stays. Add a *why* line whenever the change
  is not self-evident from the summary; that judgement is a review concern, not
  a machine check.
- **Filename revision matches `revision:`** — `alembic downgrade <rev>` takes the
  declared value, so a filename that disagrees sends the operator to the wrong
  file.
- **Metadata order** — `revision` → `down_revision` → `branch_labels` →
  `depends_on`, exactly as alembic generates them.
- **`upgrade()` and `downgrade()` both exist.**
- **No silent no-op `downgrade()`** — a body of `pass` claims the revision is
  reversible and then does nothing. Either reverse the change, or
  `raise NotImplementedError("<why it cannot be reversed>")` so `make migrate-down`
  fails loudly instead of lying.
- **Module constants** — `UPPER_SNAKE_CASE`, declared above the first function
  (the same rule as every other Python file, `code-layout.md`).

Revisions 31 and 32 carry a `pass` downgrade and predate this standard. They are
pushed, therefore immutable: the debt stays visible here instead of being
rewritten under everyone who already ran them.

### Never Do These

- Name a seed after its provider when it seeds an operation — the listing must say which row the file carries

- Ship a `downgrade()` whose body is a silent no-op
- Declare a module constant after the first function, or in lower case
- Rename a revision file without updating its `revision:` value
- Call `op.rename_table` without renaming the table's primary key in the same
  revision. PostgreSQL leaves every index, constraint and the pkey under the old
  name; `alembic check` compares indexes by name and pkeys not at all, so the
  pkey is the one that drifts unseen. Measured here: eleven ledgers renamed at
  revisions 136-146 kept `food_<old>_pkey`, every gate stayed green, and the next
  table to take one of those names was created as `food_item_report_pkey1`.
  `check-backend-migrations` refuses a rename that does not carry its pkey:

  ```python
  op.rename_table("food_nutrition", "food_ledger_nutrition")
  op.drop_constraint("food_nutrition_pkey", "food_ledger_nutrition", type_="primary")
  op.create_primary_key("food_ledger_nutrition_pkey", "food_ledger_nutrition", ["id"])
  ```

## A Skipped Comparison Is Not a Pass

`alembic check` needs a live database. When it cannot reach one the hook reports
`PASS: ORM/DB in sync (dormant — the database is unreachable (...))` and never the
bare pass. Measured: with `DATABASE_URL` exported to an unresolvable host, a real
added column was reported as `PASS: ORM/DB in sync` — the strongest gate in the
repository was a no-op that claimed the opposite.

## Common Pitfalls

1. **Empty migration**: model not imported in `alembic/env.py`.
2. **Missing `op.create_index`**: check that indexed columns (`name` in
   most domains) produce an index in the migration.
3. **AuditMixin columns missing**: `created_at`, `updated_at`,
   `created_by`, `updated_by` must appear in `op.create_table`.
4. **Rollback not tested**: always run `make migrate-down` then `make migrate`
   to confirm the migration is reversible.
5. **int → uuid type change**: PostgreSQL has no implicit cast and serial
   defaults (`nextval`) cannot be cast. Drop the default, use
   `postgresql_using="id::text::uuid"`, and drop the sequence:
   ```python
   op.execute(f"ALTER TABLE {table} ALTER COLUMN id DROP DEFAULT")
   op.alter_column(table, "id", existing_type=sa.INTEGER(), type_=sa.Uuid(),
                   existing_nullable=False, postgresql_using="id::text::uuid")
   op.execute(f"DROP SEQUENCE IF EXISTS {table}_id_seq")
   ```
   New tables with `Mapped[uuid.UUID]` autogenerate `sa.Uuid()` directly — no
   conversion needed.
