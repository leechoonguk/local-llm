---
description: Backend ledgers - a provider feed synced whole into a ledger through a stage, and the derived tables rebuilt off the ledgers by the derive job
globs:
      - backend/app/core/ledger.py
      - backend/app/schemas/mfds.py
      - backend/app/models/food/*.py
      - backend/app/schemas/food/*.py
      - backend/app/repositories/food/*.py
      - backend/app/services/food/*.py
      - backend/app/batch/sync_*.py
      - backend/app/batch/derive_*.py
      - .omp/hooks/lib/backend-ledger-feeds.ts
      - .omp/hooks/lib/backend-derivations.ts
alwaysApply: false
---

# Backend Ledger

A **ledger** is our copy of one provider operation's feed, written over whole
every night by that provider's sync job. A **derived table** is a function of
the ledgers, rebuilt whole by the derive job once the syncs are done. Edges
live on derived tables and never on ledgers (rule://backend-relations); the
jobs themselves follow rule://backend-batch; adopting a feed or a derivation
is the `ledger` skill.

## Three Words, Never Swapped

| Word | Means | Never |
|---|---|---|
| **migration** | an Alembic revision (`alembic/versions/`, rule://backend-migrations) | a feed pass |
| **sync** | a provider job's pass: the whole feed, walked and written over through a stage (`sync_<provider>_ledgers`, `replace_<table>_ledger`) | "migrate" or "import" a dataset |
| **derive** / **rebuild** | the derive job writing a derived table as a function of the ledgers (`derive_food_tables`, `rebuild_<table>`) | a pass, a step, a second write inside a sync |

A ledger is a copy of a feed and a derived table is a function of ledgers;
neither is "migrated" - the overloaded word read two ways to two readers
before these three were separated.

## One Call Per Record Is Not A Feed

**A feed's pass length is its record count divided by the records a call
answers**, and it is computed before a table is written. When that is days, the
feed is the wrong source: look for the bulk publication of the same records.

The standing decisions that arithmetic produced - which portal feeds which
ledger, and which source was condemned - are the `ledger` skill's record, not
this rule's: a rule states the criterion, a skill carries the outcomes. A
screen is scraped only for what nothing publishes in bulk, and the screen
transport survives with no operation using it - the reason is in
rule://backend-integration-configuration.

Measurements behind this: `decks/ledger-measurements` §5.
## An Integration Target Is A Ledger

The checks above read a job and ask whether what it names exists. The reverse
question is the one that decides whether an integration is finished: **every
seeded operation that pages is a feed some provider job walks.** Seeding the
provider, the operation and its fields (`integration` skill) is the first half
of adopting a dataset; the table, its `replace_<table>_ledger` and the `Feed`
in `sync_<provider>_ledgers.py` (`ledger` skill) are the second half, and a
change that ships the first without the second leaves a feed the database
never holds. Two operations on this tree were seeded and then read by no job
for the whole life of the five-jobs design - nothing asked until the check
first ran and named both (their ledgers landed the same week:
`decks/harness-history`).

Paging is the criterion, not existence. An operation whose caller inputs carry
no `range_start`/`page_no` is a lookup the API answers per call (a barcode, a
report number), and a lookup has no feed to replace a ledger with; it is not
asked for one. An operation that pages is a feed by construction — the portal
publishes it whole, in windows — and a feed that is not walked is data that was
worth seeding and not worth keeping, which is not a position anyone took on
purpose.

The pair is held both ways: a `Feed` names an operation of the job's own
provider (the walk resolves `(provider, operation)` together, and a feed of
another provider fails at 03:00 on configuration), and each seeded paging
operation appears in exactly the job of its provider — the operation's
provider is read off its seed's `PROVIDER_ID`, renames followed, so the
nutrition operations answer `data-go-kr` and not the code their seed string
still says.

## The Configuration A Job Names Must Exist

`PROVIDER_CODE` and every feed's operation code are resolved at 03:00 against
`integration_provider` / `integration_operation`. Nothing else in the stack ties
them to a row: the job type-checks and its tests script the seam without looking
the codes up, so a code no revision seeds leaves every gate green. The failure
then surfaces once a night, in a scheduler log, as configuration that
does not exist.

So `check-backend-ledger` reads the seeded codes out of `alembic/versions/` (not
out of the running database, so a fresh clone answers the same) and refuses a
provider job naming a provider or a feed that no revision inserts. It also reads
each feed's paging family off the seeded caller inputs and refuses a tuple that
mixes them: one job asks every feed for the same window, so a RANGE feed and a
PAGE feed belong to different jobs. A maintenance job, which walks nothing, is
not asked.

**A code arrives two ways, and the check reads both.** A provider can be
renamed through `provider.update().values(code=CODE)` with no insert anywhere,
and a reader that knew only `bulk_insert` calls the renamed code unseeded - a
false positive against a row every migrated database carries. The extractor
follows renames, resolves one constant indirection, and drops the code the
downgrade restores: that one is no longer in any database, and listing it
would accept a job naming a provider that stopped existing.

## A Check Names Things That Exist

Every ledger fact this harness knows comes from one reader,
`hooks/lib/backend-ledger-feeds.ts`, which parses the `FEEDS` tuple of each
`sync_<provider>_ledgers.py` into `{provider, operation, service,
replace, domain, table}`. The read-only router (`check-backend-domain`), the
ledger list screen (`check-frontend-screens`) and the frontend domain shape
(`check-frontend-domain`) all ask it, so a job may hold several ledgers and no
check derives a table from a file name. A `Feed(...)` the reader cannot place —
a service not imported from `app.services.<domain>.<table>` - is reported by
`check-backend-ledger` rather than silently dropped, so the reader cannot go
blind on a rename: a reader that drops what it cannot place switches every
downstream invariant off and stays green.

## The Ledger Reads Exactly What The Operation Answers

`from_record` is a list of `record.get("<key>")` calls over a `Mapping[str,
object]`, and nothing types the key: a misspelt one reads `None`, the column is
NULL on every record forever, and the run reports success. The reverse drift is
quieter — a key added to the seed that the ledger never reads is data the sync
drops.

**The reading is the field's type, not a helper per column.** A provider's wire
dialect - its empty strings, its clock, its date forms - is a set of `Annotated`
types in `schemas/<provider>.py` (`MfdsText`, `MfdsKeyText`, `MfdsDatetime`) plus
a record base (`MfdsRecord`) the ledger's `*Mutable` model extends; `from_record`
hands `record.get("<key>")` to `cls.model_validate` raw and the type normalises
it. The alternative this rule retired was a helper per column - a wrapper that
laundered `object` into `str | None` for the type checker, normalised nothing a
type could not, and lived in `core/` because a schema may not export a
function. `check-backend-ledger`
refuses a `from_record` that does not build through `model_validate` or that
wraps a `record.get()` in anything but the class's own key guard (`cls.key_text`)
or a module-private helper for one column's own oddity (`_amount`).

`check-backend-ledger` reads each feed's seeded `RESPONSE_ROWS` and checks the
schema of the table the feed's service names (`app/schemas/<domain>/<table>.py`)
both ways. A key the ledger declines on purpose (`row_no`,
the record's position inside its page) is declared in an `UNSTORED_KEYS`
frozenset beside `from_record`, with the reason - so a decline is a decision the
check can tell from a column that was forgotten.

## A Sync Walks Positions, Never A Filter

A pass is windows of `PAGE_SIZE` from the first row, and nothing else - or, for
a **file feed** (`response_format` CSV), the portal's whole file read in chunks
of `PAGE_SIZE` rows, which is the same pass with the windows drawn by the reader
instead of the portal (rule://backend-integration-configuration, "A File Is a
Transport"). A file feed seeds no paging inputs and no filter at all; the walk
asks nothing of it but the file. It exists for the feed a day's quota cannot
window - 2,047 windows against ~500 calls a key - and the job, the stage and the
floor read it exactly as they read a page. Every
operation here seeds optional caller inputs beside its paging keys (`change_date`, `changed_from`, `last_updated_from`, `update_date`,
a product name, a licence number), and each reads a **subset**. A job that sent
one would import what matched and call the ledger complete.

The temptation is real, not hypothetical: a portal that caps unfiltered calls
per hour while exempting a date filter invites the narrow walk, and the date
filter reads a few thousand rows where the feed holds a million. The answer is
to pay the quota in hours - the walk waits it out - not to narrow the walk.

`check-backend-ledger` reads each feed's seeded caller inputs and fails a
provider job whose module sends any key outside the paging family.

## The Floor Refuses A Pass That Is Not A Feed

A provider's ceiling is silent on one family: data.go.kr answers `num_of_rows`
past its cap with HTTP 200 and an empty list - the same shape as the end of
the feed. A job past the ceiling reads nothing, stops on its "short" first
page and would report success every night, and no other gate sees it because
the call succeeded. (RANGE refuses out loud: `ERROR-336` past its cap.)

The seed carries no ceiling, so the guard is where the pass lands: `LedgerStage.
replace` refuses a pass **under the floor** (half the live rows, `DEFAULT_FLOOR`)
and refuses an **empty pass whatever the ledger holds** — a feed that answered
no rows at all is a window past the ceiling, not a first load, and the first
night is the one nothing else would catch. Either refusal raises
`LedgerFloorError` with both counts, the ledger stays as it was, and the feed's
night is FAILED. `PAGE_SIZE` is therefore the portal's measured cap, written
once per provider job with its evidence beside it, and never a parameter.

## A Quota Is Neither The End Nor A Failure

A quota answer is **a wait**: the walk rotates to the next key of the pool
(`integration_secret.rotation_group`) and, with every key spent, sleeps until
the earliest `retry_at` and asks for the same window again. Read as a failure,
the load dies at the quota every hour; read as the end of the feed, the ledger
is replaced with the windows walked before it.

A time-of-day limit is a quota code too: a portal shut for its own working day
(식품안전나라, `ERROR-503` 09:00-19:00 KST) seeds that code with the length of
the shut period, and the walk waits it out like any other quota.

The reading lives in one place, `IntegrationOperationService.walk_operation`:
the quota code is seeded on the operation. A job names no quota code and counts
no windows.

Measurements behind this (which portals refuse, what a pass then costs):
`decks/ledger-measurements` §1.

## A Job Walks One Ledger

The identity chain — module = function = `BATCH_JOBS` key = seeded
`batch_schedule.code` — is self-consistent by construction, so it stays green
while the thing the job *reads* is renamed underneath it: a renamed ledger can
leave every one of the five names stale together with every gate passing.

So a job is named after the ledger it owns: `app/batch/sync_<table>.py`, where
`<table>` is the table itself — `sync_food_ledger_recall` fills
`food_ledger_recall`, `SYNCED_BY` reads `batch:sync_food_ledger_recall`, its
test is `tests/batch/test_sync_food_ledger_recall.py`, and its schedule row
carries the same code.

**One job walks one feed**, because a night holds one walk: a portal shut for
its own working day leaves a night shorter than one provider's feeds laid end
to end. Separate jobs take separate nights (which portal, and the hours:
`decks/ledger-measurements` §8).

**The jobs of one provider are serial.** `JOB_PROVIDERS` maps each job code to
its provider and `BatchScheduler` holds one lock per provider across the whole
walk: two ledgers of one portal take turns, two portals overlap. The queue is
one lock deep, so a feed waits only for whatever is actually walking.

A renamed job code is a data migration, not just a rename: the schedule is a row
(`batch_schedule.code`), so Python alone would leave every environment running a
row whose code names a module that no longer exists. `seededBatchCodes()` reads
updates as well as inserts for the same reason — a renamed code is scheduled, and
a reader that knew only `bulk_insert` called it unseeded.

## A Ledger Job States Facts, Not Knobs

A ledger job has **no knob and no parameter**. What it states are facts about
the portal, one each, and `check-backend-ledger` requires all of them:

- **`PROVIDER_CODE`** — the job names configuration, never a URL. The path, the
  key, the filters and the paging family live in `integration_field`.
- **`PAGE_SIZE`** — the portal's cap on one call, measured and cited beside it
  (식품안전나라: 1000, `ERROR-336`; data.go.kr: 500, silent). One for every
  feed, and every `walk_operation` call passes `page_size=PAGE_SIZE`.
- **`END_CODES`** — what the portal answers past its last row (`INFO-200`), or
  empty when it answers a short page; every call passes `end_codes=END_CODES`.
- **`SYNCED_BY`** — `batch:<job>`, what the rows say wrote them.
- **`FEED`** — one `Feed(<operation>, <Service>,
  <Service>.replace_<table>_ledger)`: the operation this job walks and the
  ledger it fills. Three elements, never four: how the feed is *addressed* is
  not the job's fact (see below).

## A Portal's Own Fact Is Configuration

Width (`page_size`), quota waits (`quota_codes`) and now **how a feed is
addressed** (`segment_key`, `segment_values`) live on the
`integration_operation` row. The walk reads them; no job states them, and the
walk never learns what a coordinate *is*: the values are listed on the row, so
code that would have to know a 보고년도 counts upward while a region code does not
never exists. A listed value the service has not opened yet costs one window of
one row and is skipped, so a year can be on the row before the portal opens it.
The pair is **seeded by a migration and has no API writer**: it is an option on
how a pass is addressed, never a selection of what the pass reads.

A service that publishes one set per coordinate (생산실적 per 보고년도) is walked
once per value, every value's pages landing in the one stage before the one
replace — so the ledger is still the whole feed. The coordinate is not a filter
and not a preference: this gateway scans the OFFSET it is handed, so a window's
cost grows with the rows already passed and a walk's with the **square** of its
windows. Restarting the offset per coordinate is what keeps a large feed
walkable — measured inside one year of I0300 (1,034,296 rows): 0.92 s per window
at offset 0, 6.36 s past 1,000,000, which is ~6 h year by year against ~48 h
flat (`decks/ledger-measurements` §13).

The failure mode is why this is a rule rather than a preference: a coordinate
that goes missing does not raise — it walks, eight times slower, and the only
sign is the clock. `check-backend-ledger` therefore closes the whole class
rather than the one instance:

| Refused | Because |
|---|---|
| a sixth module constant in a ledger job | a job owns five names (`PROVIDER_CODE`, `PAGE_SIZE`, `END_CODES`, `SYNCED_BY`, `FEED`); anything else it would say about a service is that service's row |
| a `Feed(...)` with a fourth element | the tuple is the job's three facts; addressing is not one of them |
| a calendar year in `app/batch/` or `app/services/batch/` code | the shape the coordinate first arrived in — docstrings, where measurements are cited, are exempt |

The first row is the general one: a region code, a category or a next portal's
coordinate is refused by the same check that refuses a year, before anyone has
to notice it is the same mistake.

The body is not the job's: every ledger job ends in a call to
`sync_ledger` (`app/services/batch/ledger_feed.py`), which owns the pinned
ledger session, the call session, the step per window and the failure — one
body, twenty-eight callers.

Nothing else — and "nothing else" is checked as a whitelist, not a list of bad
names: those five are every module constant a ledger job may declare. `MAX_*`, a
cursor and `total_count` (some operations report a fixed `1` whatever the set
holds) are still named in the check for the message they give, but a name nobody
thought to blacklist is refused too.

## A Sync Is The Whole Feed, Written Over Through A Stage

A ledger is our copy of a provider's feed, so the ledger after a pass *is* the
pass. Each feed is read from row 1 in windows of `PAGE_SIZE` until a page comes
back short (or the portal answers `END_CODES`), every page is staged as it
arrives, and the ledger is then written the way it was read, in two set
statements inside one transaction (`app/core/ledger.py`, `LedgerStage.replace`):

| Statement | Rows |
|---|---|
| `DELETE` | every row of the ledger |
| `INSERT … SELECT` | every row of the stage, `created_by`/`updated_by` = the pass's actor |

`DELETE`, not `TRUNCATE`: a truncate takes the lock that blocks every reader
for the length of the insert, a delete leaves them the old rows until the
commit (and SQLite, where the tests run, has no truncate). One mechanism, so
one meaning per column: `created_at`/`updated_at` are when the pass wrote the
ledger, `version` is always 1, and nothing tells a re-sent row from a changed
one - nothing follows a change column. (The three-statement merge that kept
`version` honest - `DELETE` the gone, `UPDATE` the differing, `INSERT` the new
- was rejected for this: a table split off two ledgers wants the same write,
and a second way to fill a ledger was one more than the job needs.)

Why a stage and not a transaction around the walk: a pass over a million rows
spans hours and quota waits, and a reader must see the old ledger or the new
one, never a mix. The stage is a `TEMP` table, which lives on the connection
that created it — so the ledger session is pinned to one connection
(`AsyncSession(engine.connect())`, refused otherwise) and the calls get a
session of their own. `create()` drops a stage a dead pass left behind.

Why rows keep their `id` when every row is deleted nightly: the stage mints it
from the natural key (`LedgerStage._row_id`, `uuid5` of the table name and the
key parts), so the same record gets the same id on every pass and on every
host, and a bookmark taken from one night's ledger finds its row in the next.

Every feed's service exposes `replace_<table>_ledger(pages, synced_by, *,
floor)` and nothing else writes a ledger; it returns `(received, written)` —
records read, rows the ledger holds afterwards — and the job returns `written`
summed over its feeds. A record with no natural key is skipped where it is
read, and a key the pass already staged is staged once, so `written` is the
pass minus the skipped and the repeated. Which reading stands is the stage's
`newest` column when the feed carries revisions - a portal that re-sends one
key under several revision stamps, the oldest an empty shell, takes
`newest="source_updated_at"` and the greatest stamp wins, in a page or across
pages, a stamp over none - and the first reading otherwise, since a provider
that only re-sends across shifting windows hands over the same record both
times. A ledger that keeps the first reading of a revised record shows the
shell and not the product: check a new feed's repeats before choosing (which
feeds here carry revisions, and the counts, are the `ledger` skill's record
and `decks/ledger-measurements`).

**A finished feed is its ledger's night, and a failed feed is not the run's.**
The job catches `IntegrationError` and `LedgerFloorError` per feed, leaves that
ledger as it was, goes on to the next, and raises the first failure once every
feed had its turn — so the run reads FAILED and the other ledgers are still
tonight's.

## A Derivation Stands Down While A Ledger Is Being Walked

`derive_food_tables` fires every day and lists every ledger job in
`DEPENDENCIES`. One of them in flight means the ledgers are about to change, so
the run ends **SKIPPED** with the reason (`BatchSkippedError`) rather than
rebuilding against a half-walked week or reporting a rebuild that found
nothing. A job that *failed* is not waited for: its ledger is last week's,
whole, and a derivation is a function of whatever the ledgers hold.

## A Derived Table Is A Function Of The Ledgers

A table no operation answers but that is read off the ledgers - the report
table (two ledgers under one `report_kind`), the ingredient split (two
comma-joined lists into rows), the classification tree minus its retired
nodes, the raw materials minus the classes nothing eaten is made of, the five
standard tables and the nutrition table copied whole so their edges can live
here (rule://backend-relations) - is **derived**: not a `Feed`, not a job
step, and not a ledger service's business.

The retired shape - each table written inside its ledger's pass, in the
ledger's transaction - had three costs: a rule that changed (which
classification nodes are in the 공전) waited for the next walk of the feed -
hours and quota - to reach the table; ledger services each carried a second
stage for a table that was not theirs; and a table read off two ledgers could
never join them, since neither pass knows whether the other has landed.

So a derived table is a `Derivation(<Svc>, <Svc>.rebuild_<table>)` of
`derive_food_tables`, and the contract is the same for every one:

| | A derived table |
|---|---|
| Model | `models/food/<table>.py` - the table name without the `ledger_` prefix; `NATURAL_KEY` on the model, since nothing but the derive job writes it |
| Columns | the ledger's own, read through `synced_columns(Model, NATURAL_KEY)` - every column the model declares beyond its key and the audit trail, so a column added to both is carried and one added to only one fails at the first rebuild instead of staying NULL; a computed column (`report_kind`, `base_code`) is filled by the service's row function beside them |
| Service | `services/food/<table>.py`, one method: `rebuild_<table>(synced_by) -> int`, which reads the live ledgers in keyed pages (`core.ledger.scan_table`), stages what the table is a function of, and writes it over whole (`LedgerStage.replace`, `floor=None` - the ledgers' own floors already vouched for the rows; a ledger whose records carry no list yields a legitimately empty derivation) |
| Reads | ledgers only. A derivation that read another derived table would depend on the order of `DERIVATIONS` at write time, and the order is a read-time promise (below), not a write-time one |
| Filter | stated once, as a module-private predicate with the measured count beside it in the service; a rule that changes is a rebuild, not a walk of the feed |
| Order | `DERIVATIONS` lists targets before sources: a reader of the graph after the run finds every edge's target rebuilt no later than its source |
| Evidence | the model docstring states what the derivation keeps and drops, with the count and the date; an edge states its coverage the same way (rule://backend-relations) |

Idempotent by construction, so a rule change is `POST /batch/{id}/run` on the
derive job, minutes off the live ledgers (timings:
`decks/ledger-measurements`). The job waits for its `DEPENDENCIES`' night to
be over - a provider job with a run in flight is about to replace the ledgers
it reads - and does not wait for a feed that *failed*: that ledger is last
night's, whole, and the derivation is a function of whatever the ledgers hold.
`check-backend-ledger` refuses a derived model that no `Derivation` rebuilds
(a table nobody rebuilds is empty forever, with every other gate green), a
derivation whose service reads a table that is not a ledger, and a
rebuild method that is not `rebuild_<table>(self, synced_by)`.

## A Derived Column Means What Its Registry Said

The meaning of a derived column is the statement of the registry the ledger
copied. Two consequences, and they pull in opposite directions:

- **Same registry, two places is duplication.** One fact of one ledger is
  written once, in the table whose row it belongs to. The 수입 registry's
  유통기한 is a range between two dates and lives on the declaration that
  declared it (`food_item_report_declaration.expiry_from`/`expiry_to`), so
  `food_item_report.shelf_life` - a *period* a domestic report states
  ('제조일로부터 12개월') - is NULL on every import row. When one name held
  both facts, a reader could not tell which they had.
- **Different registries, same name is not duplication.** C005 publishes a
  제품명 for a barcode and I1250 publishes one for the report; they agree the
  overwhelming share of the time (rate: `decks/ledger-measurements`) and the
  disagreement is the registries', not an error to be overwritten. Each stays
  on its own derived table, and the docstring says whose words they are.
- **A ledger may hold more than products, and the product boundary is the
  ledger model's own constant.** The 수입신고 ledger is every crossing of the
  border and states one of seven 제품구분; a product is what a registry can
  name under a 식품유형, and only 가공식품·식품첨가물·건강기능식품 use the
  식품공전 vocabulary the other registries do (measured: 95 %, 82 %, 48 % of
  their rows share it; 농·수산물 0 % - `브로콜리(신선)` is an HS commodity,
  축산물 19 % - `돼지고기(냉동,정육…)` is a quarantine class, 기구·용기·포장
  is not food). `PRODUCT_DECLARATION_KINDS` on the ledger model is the
  boundary, and every derivation that reads the ledger - the product, its
  declarations, its labels, its ingredients, and the lot index an event
  resolves through - passes it to `scan_table` as `where`. One constant, six
  readers: a reader that forgot it would derive rows no product carries. The
  other four kinds stay in the ledger whole and reach no derived table.

**Vocabulary is unified when the role is the same.** A column that means
보고일자 is `report_date` wherever it is written - `food_barcode.permit_date`
was renamed for that reason; nothing there is a permit.

**An edge to a product carries both key columns.** `food_item_report` is keyed
by `(report_kind, item_report_no)` because four registries number in separate
spaces, so a relationship or a join written on `item_report_no` alone points at
whichever registry's row was written first. A feed that publishes the number
and not the registry - C005, I2790, the 푸드QR and HACCP label feeds - has its
kind **resolved at derive time** against the numbered report ledgers, and a
number no registry carries stays NULL rather than guessing.
`check-backend-relations` refuses the one-column form.

## One Splitter For Every Joined List

A provider's list arrives as one string, and how it is punctuated is the
provider's business: `()` on all five lists this repository reads, `{}`, `[]`
and `<>` on the 건강기능식품 ones, the full-width forms, and a thousands comma
inside a quantity. **The depth-counting split lives in one function** -
`core.printed_label.split_list` - and every list goes through it: the 원재료
columns of C002 and C006, the three 건강기능식품 lists, the registry's own 이명
column, the printed 원재료 paragraph, the HACCP 알레르기 string (which passes its
own separators; which characters end an item is a caller's fact, how depth is
counted is not).

Two splitters in one tree is how fragments are minted: a service that counts
`()` only cuts a `{}`-wrapped item at its inner commas into bare numbers,
units and stray braces, while `printed_label` counts six bracket kinds for the
same paragraphs (fragment counts: `decks/ledger-measurements`).
`check-backend-ledger` refuses a second splitter: a
`.split(",")` over a provider's list, or a separator read at depth zero outside
that function.

**A normalisation rule earns its place with a count.** A candidate rule is
measured against the live names before it is written - what it strips, how
many rows carry it, and what resolution it buys or costs; a strip that drops
resolution is the registry's own word, not noise. The measurement sits in the
service where the rule would live (`services/food/item_report_ingredient`),
where the next reader will look for it.
Names the 원재료 dictionary does not carry stay NULL - no code is forced onto a
name (rule://backend-relations).

## A Table Family Of One Paragraph Is One Derivation

One table, one `rebuild_<table>` - unless several tables are the same reading of
the same source under the same key. The import label family is that case:
`food_label` is the printed paragraph and `food_label_allergen`,
`food_label_caution` and `food_label_packaging` are the lists inside it, all
four keyed by the product the paragraph was printed for.

Before the family rule, six derivations each walked the million-row 수입신고
ledger whole, each picked the representative declaration again (`keep_newest`)
and parsed the same paragraph again - six scans and six parses per derive run
for four tables and one ingredient split that are one reading. After:
`FoodLabelFamilyService.rebuild_label_family` scans once, parses once and
writes the four tables through four stages in one pass, and the ingredient
split reads the same selection rule from `core/printed_label.keep_newest` -
two scans, one parse per label.

So the contract widens by exactly one clause: **a family of tables read out of
one record under one key is written by one derivation**, named
`rebuild_<name>_family`, which imports the derived models it writes and stages
each as its own table (a floor refusal stays that table's). Every other derived
table keeps the one-table rule; a second derivation writing a table another one
already writes is still refused, because two writers of one table is the defect
the rule exists for. `check-backend-ledger` reads a family's tables off its
imports (`hooks/lib/backend-derivations.ts`), so a model it does not import is
still "rebuilt by no derive job".

## Validation (Post-Hook)

`check-backend-ledger.ts` enforces the feed → ledger → derived chain, because
every missing link fails **silently** - each row below was reproduced by
deleting the link and watching the gate go red:

| Link | Checked | Without the check |
|---|---|---|
| a provider job has the provider shape | `sync_<provider>_ledgers.py` with `PROVIDER_CODE`/`PAGE_SIZE`/`END_CODES`/`SYNCED_BY`/`FEEDS`, name held to the code, no `MAX_*`/cursor/`total_count` in code | five settings drift five ways, and a ceiling or a count comes back as a "guard" that hides the floor |
| every feed replaces its own table | `Feed(op, Svc, Svc.replace_<table>_ledger)` where `Svc` is imported from `app.services.<domain>.<table>` | a feed replaced through another table's method, or outside `LedgerStage`, has no floor |
| every walk asks the same window | each `walk_operation` call passes `page_size=PAGE_SIZE` and `end_codes=END_CODES` | one feed pages alone and reads its end differently |
| the provider and every feed are seeded, and page alike | codes read from `alembic/versions/`; families read from seeded caller inputs, a CSV seed reading as `FILE` | configuration that does not exist fails at 03:00; a RANGE feed asked for `page_no` reads nothing |
| every feed is the job's provider's | each `Feed` operation's seed names the job's `PROVIDER_CODE` (renames followed) | `(provider, operation)` resolves to no row, once a night |
| every seeded paging operation is a feed | configured operations with `range_start`/`page_no` among caller inputs, or seeded `CSV`, ⇔ a `Feed` in some `sync_*_ledgers.py`; the message names the job it belongs in | an integration is "done" at the seed, and the dataset it was seeded for is never held |
| every derived table is a derivation | each `models/food/<table>.py` without the `ledger_` prefix ⇔ a `Derivation(<Svc>, <Svc>.rebuild_<table>)` in some `derive_*.py`, `<Svc>` imported from `app.services.food.<table>` | a derived table nobody rebuilds is empty forever, and every screen on it is green on nothing |
| the ledger reads what its feed answers | `record.get("key")` in `app/schemas/<domain>/<table>.py` ⇔ seeded response keys, minus `UNSTORED_KEYS` | a misspelt key is NULL forever; a new key is dropped |
| a pass walks positions | no seeded caller input outside the paging keys is sent | a filter imports a subset and calls it the ledger |
| feeds fail alone | `LedgerFloorError` is caught in a job that walks | one feed's bad night empties nothing but ends every other feed's night too |
| a derivation reads ledgers only | `services/food/<table>.py` (no `ledger_` prefix) names no `Food*` model that is not `FoodLedger*` in a `scan_table(` call | a derived table depends on the write order of the run, and a reorder empties it |
| a rebuild has the one signature | `async def rebuild_<table>(self, synced_by: str) -> int` in that service, `<table>` the file stem | the job registry calls a method the service does not have, once a night |

Every ledger fact these checks know comes from `hooks/lib/backend-ledger-feeds.ts`
(the `FEEDS` reader) and `hooks/lib/backend-derivations.ts` (the `DERIVATIONS`
reader); the batch, domain and frontend checks ask the same readers, so no
check derives a table from a file name.

## A Refused Branch Leaves Its Measurement

A read that a rule allows but no data reaches is not implemented: it is green
on invented fixtures only. Before a branch, an edge or a column is written,
measure how many live rows reach it; when the answer is none, do not write it.

The number that decided it goes in two places and neither is this file: a dated
one-liner in the docstring where the code would go, and a slide in
`decks/ledger-measurements`. A decision without its number is re-measured by
whoever asks next; a rule carrying every past number stops reading as a
contract.

## Never Do These

- Send a seeded caller input outside the paging family from a sync - a filter
  imports a subset and calls it the ledger.
- Add a knob, a cursor, a `MAX_*` or a `total_count` to a provider job - the
  portal's facts are stated once each, and the floor is the guard.
- Write a derived table inside a ledger's pass, or make a derivation read
  another derived table.
- List a derived table's columns by hand in its service - `synced_columns` reads
  them off the model.
- Fill a ledger any way but `replace_<table>_ledger` through `LedgerStage`.
- Call a sync or a rebuild a migration.
- Remove or decline a branch, an edge or a column without leaving the dated
  measurement that decided it beside where it would be added.
