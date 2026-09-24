---
description: Backend relations — a ledger is no edge's endpoint; an edge joins two derived tables, and a ledger fact reaches them as a column its feed's pass fills
globs:
      - backend/app/models/food/*.py
      - backend/app/repositories/food/*.py
      - backend/app/services/food/*.py
      - .omp/hooks/lib/backend-relations.ts
alwaysApply: false
---

# Backend Relations

## The Rule

**A ledger is not an endpoint of any edge. It declares no `relationship()`, and
no `relationship()` points at it. An edge joins two derived tables —
`viewonly=True`, with a `primaryjoin` that spells the columns once.**

```python
class FoodItemReportIngredient(Base, AuditMixin):   # derived
    report: Mapped[FoodItemReport | None] = relationship(   # derived, too
        primaryjoin=lambda: and_(
            foreign(FoodItemReportIngredient.report_kind) == FoodItemReport.report_kind,
            foreign(FoodItemReportIngredient.item_report_no) == FoodItemReport.item_report_no,
        ),
        viewonly=True,
        lazy="raise_on_sql",
    )
```

**A ledger is read one table at a time.** What it holds reaches a derived table
through its feed's pass — the pass that builds the derived row — not through a
join at query time.

## Why

A ledger is one feed's copy: `LedgerStage.replace` deletes every row and inserts
the pass, nightly, per feed. A `ForeignKey` between two would make one feed's
pass fail on the other's gaps — measured:
`food_ledger_common_standard.common_standard_type_code` names a group the type feed does
not carry on roughly a quarter of its rows. That much was already true when the edges
lived on the ledgers.

What the ledgers' own edges added was a second thing: **a claim about which
questions matter, made by the table that only stores answers.** Measured:
fourteen relationships were declared across the ledger models and
*none* of them was read outside the tests — no repository, service, batch job or
router joined along one. They were a query layer nobody had written, kept in the
schema, and every provider gap had to be argued in a comment beside an edge that
served no caller.

The edges that pointed *into* a ledger from a derived table went for the second
half of the same reason. A derived table is built by the passes that write the
ledgers, in their transaction: whatever it needs from a ledger row it can be
given as a column, once, at write time — where the pass already holds the row and
where a gap can be counted. Read at query time instead, the same fact costs a
join per read and its coverage is a number nobody measured. So the schema has
one wall: ledgers on one side, and on the other a graph of derived tables that
the screens actually walk.
## Names

| | Prefix | Written by | Declares edges |
|---|---|---|---|
| Ledger | `food_ledger_*` | one portal operation's pass, wholesale | never |
| Derived | `food_*` | `derive_food_tables`, whole, off the ledgers | yes, to other derived tables |

The prefix keeps the bare names for the layer a router speaks:
`food_ledger_nutrition` is I2790's copy, `food_nutrition` would be what a screen
asks for.

## The edge (between derived tables)

- `primaryjoin=lambda: ...` — a lambda, so the other model is named at mapper
  configuration and the food models need no import order. The local column is
  wrapped in `foreign(...)`: without a constraint that is the only way the
  mapper knows which side the key is on.
  A **back-reference** is the exception: the child imports the parent's module,
  so the parent cannot name the child at runtime and spells `primaryjoin` and
  `order_by` as strings the registry resolves (`FoodItemReport.ingredients`).
  The annotation comes from a `TYPE_CHECKING` import (`backend-model-files.md`).
- `viewonly=True` — the edge is read, never written through; a derived row is
  written by the pass that builds it alone.
- `lazy="raise_on_sql"` — as every relationship in this tree
  (`backend-domain.md`).
- A list-valued edge (`Mapped[list[...]]`) says `uselist=True`. Measured:
  with `foreign()` on the local side the mapper reads the edge as
  many-to-one and hands back one object under a `list` annotation, silently.
- A slice is part of the join (`and_(Model.report_kind == FOOD_KIND, ...)`): the
  edge is defined on the slice, so the slice is in the edge.
- A self edge on a derived tree says `remote_side=lambda: Model.code`, and a
  query joins it through an alias (`.outerjoin(Model.parent.of_type(aliased(Model)))`).
- Every edge carries the reading it was declared on, in the comment above it:
  how many rows of this table resolve to one row, to none, to several, **with
  the date it was measured**. `check-backend-relations` refuses an edge whose
  comment block carries no `YYYY-MM-DD` and no number: an edge without a
  constraint is a claim about two tables' data, the claim is the count, and a
  count without a date cannot be told from a stale one. Measured before the
  rule: an ingredient edge read as "resolves" until the count said 18.5 %, and
  it was removed on that number; an exemption edge sat at 0 of 21 for a day
  with nothing saying so.

## What a ledger fact costs at write time instead

A derived table is built inside the pass that writes a ledger, so a fact that
*would* have been a join is a column the pass fills - once per night, where the
row is already in hand and where the misses can be counted. That is why
`food_item_report` carries C006's six answerable columns and eleven NULLs rather
than an edge to C006: the NULLs are a measured 34.6 % of rows, and a join would
have hidden the same gap behind a LEFT.

## LEFT at the call

`relationship()` has no join type; the query chooses. A derived row whose key the
other derived table does not carry is still a row, so the default reading is
`outerjoin` / `joinedload` (LEFT), and an `INNER` join is a filter the query
means.

## The key column a derivation has to resolve

`food_item_report` is keyed by (`report_kind`, `item_report_no`) and four
registries number in separate spaces, so a derivation holding a bare
품목제조보고번호 must ask which registry it belongs to before it can join. Three
do it, each the same way: a module `REGISTRIES` tuple of (ledger, kind) and a
`_registry()` that reads the numbers off those ledgers.

**The lookup is only as complete as that tuple, and an incomplete one does not
fail — it resolves to nothing.** Measured: `safety_record` named two registries
where its siblings named three, so every 수거검사 of a 건강기능식품 — 18,536
records of 5,648 products — carried its number with no kind, and the read layer
dropped them as naming no product we hold. Every gate was green: each kind it
did write was legal, the edge was declared correctly, and nothing compared the
three tuples with each other.

So they are compared — against the owner, not against each other. The expected
set is the ledgers the owner derivation reads to build the product table; a
derivation short of it declares the omission and the reason:

```python
UNRESOLVED_REGISTRIES = {"FoodLedgerImportFoodLabel": "번호가 아니라 (수입업체, 로트일자)로 붙는다"}
```

수입식품 is the standing example: it numbers a product by a digest this codebase
mints, so no published record can carry one and nothing would ever resolve
against it *by number*. That is a decision, not an omission — and a decision is
written down.

**An import event reaches its product the way the portal reaches it: by the
lot.** The portal keys an import by the 수입신고 — one declaration of one
product, on one lot — and hangs a recall on that declaration, not on the
product (measured: one recall on one of a product's six declarations, the one
whose 소비기한 starts on the day the recall prints as 제조일자; the deck's §18).
So `safety_record` reads that day into `lot_date`, looks `(수입업체, lot_date)`
up in the declaration ledger, and takes the product only where the name picks
one or the lot holds one; the declaration itself is never stored on the record
— the declarations tab finds it back by `(item_report_no, lot_date =
expiry_from)` at read time. A recall with no single date ("데이터없음", a range)
resolves to nothing, because an event put on a lot the feed never named is a
guess in a column a screen joins on.

## The domain is discovered, never named

`food` is one ledger domain, not the definition of one. A check that spells it
out is a check a second domain passes by being invisible to it — the same shape
as the defect above, one level up. So nothing in the hook names `food`:

| What was a constant | How it is found |
|---|---|
| the domain folder | a folder under `models/` holding a `__tablename__ = "<folder>_ledger_…"` |
| `FoodLedger*` | the folder's name in PascalCase + `Ledger` |
| the owner `item_report.py` | the domain's derived table whose `NATURAL_KEY` is exactly (kind, number) and whose `CheckConstraint` closes the kind |
| the product edge | that owner's class and its two key columns |

**A ledger table's prefix is the folder it lives in.** That agreement is what
makes discovery possible, so it is checked: `pharma_ledger_x` under
`models/food/` belongs to a domain that does not exist, and would be read by
nothing.

**Discovery that finds nothing says so.** A domain whose derivations resolve
registries while no owner can be found — or where two tables have the owner's
shape — is a finding, not a quiet pass. Otherwise a rename of `NATURAL_KEY`
turns the whole comparison off and every gate stays green.

## Validation (Post-Hook)

`check-backend-relations` reads every discovered ledger domain and the query layers:

- no model under a domain folder declares a `ForeignKey`;
- no ledger model (`<domain>_ledger_*`) declares a `relationship()`;
- no `relationship()` in the domain targets a `<Domain>Ledger*` model;
- every relationship is `viewonly=True` and has a `primaryjoin=` that marks a
  `foreign(...)` side;
- a `Mapped[list[...]]` relationship declares `uselist=True`;
- no file in `repositories/`, `services/`, `batch/`, `routers/` or `core/` joins a
  `Food…` model by its class (`.join(FoodX, ...)`, `.outerjoin(aliased(FoodX), ...)`);
- every relationship has a dated count in the comment block above it;
- every `REGISTRIES` tuple names every ledger the owner derives the product
  from, or declares what it leaves out in `UNRESOLVED_REGISTRIES` with a reason
  — and a declaration naming no ledger model is dead;
- every ledger table sits in the folder its prefix names;
- a domain that resolves registries has exactly one discoverable owner.

## Never Do These

- Add a `ForeignKey` between any two tables of this domain.
- Declare a relationship on a ledger — the ledger stores, it does not ask.
- Point a relationship at a ledger — give the derived table the column instead,
  filled by the pass that already holds the ledger row.
- Write `.join(FoodX, FoodY.code == FoodX.code)` in a repository — declare the
  edge on the derived model and join along it (`.outerjoin(FoodY.x)`).
- Resolve a product's registry from a subset of the registries a sibling
  derivation reads — the rows of the missing one keep their number and reach no
  product, silently.
- Declare an edge without `viewonly=True` — the pass is the only writer, and a
  write through the edge would be a second one.
- Declare an edge without the reading that justifies it in the comment above.
