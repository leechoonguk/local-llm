---
description: Frontend screen types — list, form dialog, detail tabs, dashboard, auth templates
globs:
      - frontend/src/sections/**/*.tsx
      - frontend/src/pages/*.tsx
      - frontend/src/components/**/*.tsx
      - frontend/src/hooks/*.ts
alwaysApply: false
---

# Frontend Screens

Five screen types cover this application, and each has exactly one shape. A
screen is written by copying the nearest screen of its type: the similarity is
the standard, not duplication waiting to be factored away. A generic
`<CrudScreen domain={...}>` would hide the columns, the dialogs and the empty
sentence behind configuration, and the first screen needing an exception would
fork it.

Machine-checked by `check-frontend-screens.ts` (`make check-frontend-screens`)
plus `ast-grep/rules/frontend-screen/`.

## What A Row Is Decides Whose Screen It Is

A table hangs off an owner or it does not, and the answer is not the foreign
key - it is whose statement the row is. A 신고 is the product's own (its
history tab); a 검사·조치 이력 row is an authority's finding or action about the
product, read by date, kind and verdict across everything, so it is a list
screen of its own and the product's section states what its own rows add up to.

The measurement that decides it is how often the owner has any: a few hundred
events over millions of products is a column that is zero on 99.95% of rows and a
filter with nothing to type, and the same rows are a screen a reader can scan.

**A tab named for a shape it does not draw is the same defect one level up.**
The product dialog had one 이력 tab over one table of seven columns, and the
two registries fill different halves of it: a 수입식품 declares crossings
(처리일자, 수출국, 소비기한) and every other registry declares a year's figures
(보고년도, 생산량, 연간생산능력). No product carries both shapes, so three or
four cells of every row were an em dash, and the section under the tab was
headed "수입신고 이력" on a domestic product, which files no 수입신고 at all.
The registry chooses the tab's name and its columns, not just its wording.

**An action attaches to an event, never to an aggregate.** The authority's
조치 column belongs on the 수입신고 table, where a recall sits on one crossing;
a 생산실적 row is a year's total and nothing an authority did lands on it. A
column that paired them would be joining two facts that share only a year. The
asymmetry between the two tables is the asymmetry of what is being declared.

**A guarded count is not a hidden section.** The guard below is about the
*number*: "검사·조치 0" beside 1.9 M products is noise. Whether the product has
been inspected at all is not noise - 84,212 of 1,856,644 carry a record
(4.5 %), and for the rest a screen that draws nothing reads as "this screen
has no such thing" rather than "nothing was published". So the section is
drawn either way and says which: rows when there are rows, one sentence when
there are none. The sentence names the key it is true of - 이 제품 **번호로**
공표된 이력이 없다 - because two thirds of 수거검사 rows carry no 품목보고번호
at all, and "no inspection" would be a claim the data does not support. The
label card and the history tab already answer this way; the record section was
the one that vanished.

`checkSectionsAnswerWhenEmpty` refuses `{x_count > 0 && <Section/>}` with no
`x_count === 0` branch. Only a **section** owes the answer - a
`DetailSection`, a `PagedTableSection`, or a tab. An `Alert` exists because
there is something to warn about, an inner `Stack` sits inside a card already
drawn, and a `Typography` is part of a sentence; the first version of this
check required all of them to have an empty twin and fired on three screens
that had done nothing wrong.

**Presence is mechanical, wording is not.** What the section then *says* is
the component's business and no hook governs it: the history tab draws
수입신고 with six columns for an import and 생산실적 with three for a domestic
report, one section reading two registries. That is a difference of what the
row is, decided where the registry is known - not a section appearing and
disappearing.

## A Zero Is Not Information, A Date Is Not Digits

Two readings a screen owes its reader, both refused mechanically by
`check-frontend-screens`:

- **A count is drawn when there is something to count.** The product dialog drew
  "신고 건수 0 · 검사·조치 0" on every product while a fraction of products carry
  a record (84,129 of 1.9 M), so that card said zero most of the time and the
  rows it existed for were below it. A `*_count` is rendered inside its own `> 0`
  guard - the guard is looked for in the JSX block that draws it, not in the
  lines nearby, because a sibling block's guard is not this one's.
- **A registry's date is eight digits; a screen's is a date.** The ledgers store
  `20260915` verbatim, which is what a ledger is for. A field or cell holding a
  `*_date` reads it through `formatPortalDate`, and a `*_at` through
  `formatDateTime`.

  **A grid column is the same rule and was the gap.** The first check read the
  JSX (`<ClippedText text={row.event_date}>`), and a list has none: it declares
  a column and `ServerDataGrid` injects the cell, so the raw value never appears
  beside a component name. `/food/item-report` printed `20260915` under 보고일자
  and the 검사·조치 이력 list did the same under 기록일, both green. Now the column itself
  is read: a `*_date`/`*_at` field must name its formatter in `valueFormatter`
  or `renderCell`.

- **No two columns of one grid carry the same header.** A header is the only
  name a column has. The 검사·조치 이력 list headed both `record_kind` and `report_kind`
  구분 - an authority's action and the registry the product is in, under one
  word - and every gate passed because each key existed and each was translated.
  The headers are resolved per locale, because a collision in either language is
  a screen somebody reads.

## A Column Fits What It Prints

Two things in a table cannot shrink, and both are checked mechanically - no
browser, no eye:

- a **badge** (`Label` is `white-space: nowrap`, so a narrow column cuts it
  behind the cell's overflow),
- a **header name** (the grid ellipsises it, and a header nobody can read is a
  column nobody can sort).

`check-frontend-screens` turns each column's declared width back into pixels -
a grid column's `floor`, a dialog column's percentage of
`RECORD_SURFACE.TABLE_WIDTH` - and compares it with the ink of what the cell
prints: the header's locale string in **either** language, and every value of
the badge's vocabulary (the keys under the prefix the cell reads,
`t(\`item_report.kind.${row.report_kind}\`)`). The per-character ink was measured
in the running app through the canvas API (grid header `600 14px`,
badge `700 12px`) and each character class is rounded up, so the check asks for
a pixel more than the browser needs and never for less.

Measured before the rule: `/food/item-report` printed `국내 제조 식…` on every
row (the badge needs 124px, the column floored at 90), `등급 · 기관` lost its
last character on the event list, and five headers of the declarations table did
not fit their share at the English reading. Thirty-three columns across five
screens and five dialog tables were short; none of them failed any gate.

The dialog opens at `RECORD_SURFACE.DIALOG_MAX_WIDTH` for the same reason: at
`md` the seven-column declarations table had 820px to divide and needed 1,066.

## Screen Types

| Type | File | Exemplar |
|---|---|---|
| List + CRUD | `sections/<domain>/<Domain>List.tsx` | `sections/user/UserList.tsx` |
| Derived list (read-only) | `sections/<domain>/<Domain><Table>DerivedList.tsx` | `sections/food/FoodItemReportDerivedList.tsx` |
| Form dialog | `sections/<domain>/<Domain>FormDialog.tsx` | `sections/user/UserFormDialog.tsx` |
| Detail + tabs | `sections/<domain>/<Domain>DetailDialog.tsx` + `detail/*Tab.tsx` | `sections/integration/` |
| Run history | `sections/<domain>/<Domain>RunsDialog.tsx` | `sections/batch/BatchRunsDialog.tsx` |
| Dashboard | `sections/dashboard/DashboardView.tsx` | independent widgets |
| Auth | `sections/auth/LoginForm.tsx` | session, not a resource |

## Streaming Screen

A screen whose answer arrives over time - the 식품 챗 - is not a list and not a
record: no collection, no page, no filter, so none of the list template's five
pieces apply. What it owns is a transcript, one input, and the single request
in flight.

| Piece | Owns |
|---|---|
| `use<Domain>Chat` (`lib/api/hooks/`) | the transport: one turn's stream and its `AbortController` |
| `ChatConversationsProvider` (`components/chat/`) | the conversations, which one is open, and where tokens land |
| `sections/<domain>/<Domain>ChatConversation.tsx` | **both columns**: the history, the transcript, the input, the send/stop pair |
| `pages/<Domain>ChatPage.tsx` | the header and the breadcrumb, nothing else |

**One card, two columns** — the reference's chat, with its left column changed
for what this app actually has. The reference lists *people*; nobody is on the
other end here but the model, so the column lists the **conversations**, each
titled by the first thing the reader said in it and carrying the newest line
under that. The right column is the open conversation with the composer pinned
beneath it, which is why the card has a height: a composer that moves down as the
answer grows makes the reader chase the box they are typing into.

**The history lives in the screen, not in the sidebar.** It was a list of one
screen's destinations sitting among the app's destinations, and it paid for that
by having to fold itself away whenever the reader was somewhere else — a caret,
a route watcher and a render-time reset for a list that belongs to one screen.
Inside the screen it is simply always there, and the nav is a list of screens
again.

**The conversations still live above the screen** (`ChatConversationsProvider`),
because the provider is what survives navigating away and back. They are **in
memory on purpose**: no table stands behind chat and no history is sent with a
turn, so a reload starts with one empty conversation; persisting them here would
be the screen claiming a memory the server does not have. An empty conversation
is never listed — it is what the "new" button creates.

**Every turn ends on an event.** A `token` appends to the open turn, one `end`
closes it with the server's own whole answer (the authority, in case a token
was dropped), and `error` closes it with the sentence its code words. A stream
that simply stopped could not be told from a lost network, so the server never
ends one that way (rule://backend-sse). The reader's own stop is an abort, not
a failure: the turn keeps what arrived and says nothing.

Verified on screen: a turn's bubble grows character by character over frames
200ms apart - the tokens land, they do not appear at once - and stopping
mid-answer leaves what had arrived, with the send button back and no toast.

## Column Width

Every grid column has a **floor** and a **share**, and every list screen keeps
them in one table - the 품목제조보고 list's shape, copied:

```tsx
const COLUMN: Record<string, { floor: number; share: number }> = {
  username: { floor: 140, share: 1 },
  created_at: { floor: TIMESTAMP_COLUMN_FLOOR, share: 0.8 },
}
const sized = (field: keyof typeof COLUMN) => ({
  field,
  flex: COLUMN[field].share,
  minWidth: COLUMN[field].floor,
})
```

The floor is the width at which the column's widest measured value stops
clipping; the share is how much of a reader's attention the column earns, and
spare width is spread by share across **all** columns. MUI's default is 100px
with no floor, which clipped 14-character codes and `식품원료(A코드)` on the raw
material ledger; `flex` on two columns alone piled a 1920px screen's spare
width into those two while the rest stayed clipped; and a `width:` literal is a
column that cannot grow, so on a wide screen it sat at its floor while the flex
columns beside it took everything. A table puts every number in one place and
sizes every column by construction; a column spelled with its own `width`,
`flex` or a `*_WIDTH` constant is one the table does not know about.

**The timestamp floor is shared.** `formatDateTime` writes the same string on
every screen, so its floor is one number, `TIMESTAMP_COLUMN_FLOOR` in
`config.ts` - measured: `2026. 8. 30. 오후 10:57` needs 182px of cell at the
body size, and a `width: 180` on the user list clipped it to `10:...` while the
report list beside it, at 185, did not. Every `*_at` entry reads the constant.

**A column says what it shows, not how it clips.** `ServerDataGrid` injects
`ClippedText` into every column without its own `renderCell`, so a name or a
URL that overflows its share is reachable on hover by construction; a column
that spells `renderCell: <ClippedText>` itself is the grid's own default
written a second time. A `renderCell` is for a value that is not text as
stored - a badge, a formatted timestamp, a mask.

`check-frontend-screens` fails a list screen without a `COLUMN` table, a column
literal not spread from `sized(...)` (the actions column, spread from
`rowActionsColumn`, sizes itself), a `*_WIDTH` constant, and a `*_at` floor
that is not `TIMESTAMP_COLUMN_FLOOR`.

**A grid with buttons fits the card; a read-only grid may scroll.** The visible
floors plus the actions column are what the grid asks for, and the card leaves
1,080px beside the nav at 1440px. Past that a horizontal scroll opens, and the
actions column is **last** - so what falls off is the controls, and a button a
reader has to scroll sideways to find is a button they do not know exists.
Measured on `/batch`: seven floors totalling 1,132, with 실행 and 중지 outside
the card. A grid that renders no actions is not held to the
budget: the 품목 보고 list asks for 1,690px of nine columns and scrolling a wide
registry is how it is read - nothing there is unreachable, only unread.
`checkGridsFitTheirCard` computes the actions width from `rowActionsColumn`'s
own arithmetic rather than a copy of it, so a change to the button metrics
moves the budget with it.

The fix is a column, not a smaller floor: a floor is the widest measured value,
so trimming one clips what it prints. `/batch` carried a `name` beside its
`code`, and on all 33 rows the name was the code restyled
(`sync_food_ledger_recall` / "Sync food_ledger_recall") - a 217px column
carrying no fact. Dropping it end to end (column, inline edit, filter, create
field, and the table column) bought the fit and left `cron` room to stop
ellipsising `30 20 * * 0` into `30 20 * ...`.

## Derived List

The list template with its write half removed. A derived table is a function
of the ledgers, rebuilt whole by the derive job every night (a `Derivation` of
`backend/app/batch/derive_*.py`, rule://backend-ledger), so a row typed on this
screen would be gone by morning - and the backend has no verb to accept it
(`backend-domain.md`, "Ledgers Have No Route; Derived Tables Are Read-Only Over
HTTP"). A ledger itself has no screen: what a reader sees is the derived table.

Four hooks, in this order, plus the one door's state:

```tsx
const grid = useDataGridState()
const filters = useListFilters(FILTER_FIELDS, grid.resetPage)
const query = use<Domain><Table>List({ ...grid.params, ...filters.params })
const [openId, setOpenId] = useState<string | null>(null)
useQueryErrorToast(query, tCommon('messages.load_failed'))
```

What it keeps: `ListCardHead` (without `add`), `ListFilters`, `ServerDataGrid`
with `onRowClick`, `emptyTitle`, the toolbar refresh. **The row is the door**:
a row nobody edits has one verb, opening its record, so the click lands on the
row and there is no actions column to find first; the pointer cursor says so.
The door opens a read-only record dialog (`<Domain><Table>DetailDialog.tsx`,
tabs that present the record's edges through `PagedTableSection` with no
`onCreate` and no `actions`). What it refuses: `useCrudDialog`, `useToast`,
`rowActionsColumn`, `processRowUpdate`, any mutation, any form dialog.

A closed vocabulary the *schema* fixes (`ReportKind`, a `Literal` on the
server) is a select whose options are the contract's constant
(`types/<domain>.ts`), not a facets read - the values cannot change overnight,
so there is nothing to fetch. **Its options are codes, and a code owes
`optionLabel`**: a facets value is the row's own text and reads as itself, but
`food` in a Korean select is not a word (measured: it shipped that way with
every gate green, because the i18n check reads literal text and the option was
a value). `check-frontend-screens` demands `optionLabel` on any field whose
`options:` is not a `.data` read. `check-frontend-screens` reads the router's
alias for each filter off `app/dependencies/query.py` by shape: a free string
with a length floor matches by contains, everything else matches whole.

**The suffix is a claim the backend must back.** `check-frontend-screens` holds
`<Domain><Table>DerivedList.tsx` to a derivation whose service is
`app/services/<domain>/<table>.py` (`hooks/lib/backend-derivations.ts`); a
table nothing derives is edited by people and gets the CRUD template. Measured
before the rule: the CRUD check demanded `useCrudDialog` on the raw material
screen, and the only way to satisfy it was a dialog that edited rows the next
sync would erase.

## List Screen

Five hooks, in this order, and nothing else holds state:

```tsx
const grid = useDataGridState()
const filters = useListFilters(FILTER_FIELDS, grid.resetPage)
const query = use<Domain>List({ ...grid.params, ...filters.params })
const dialog = useCrudDialog<Domain>()
const toast = useToast()

useQueryErrorToast(query, tCommon('messages.load_failed'))
```

Required parts:

- `ListCardHead` — the card's head: the collection's name with the **total** as a
  badge, then one row with the filters on the left and two icons on the right,
  add then refresh. There is no labelled add button and no density control: add
  puts a row in *this* table, so it is an icon on the table's row, and density
  changed how rows look and nothing about what they are.
- `ListFilters` + `useListFilters` — one labelled box per filterable column
- `ServerDataGrid` — never MUI's `DataGrid` directly, wired to
  `grid.sortModel` / `grid.setSortModel`, and `loading={query.isFetching}` —
  every list keeps the previous page on screen while the next one loads
  (`placeholderData: (previous) => previous`), so `query.isLoading` is `true`
  only on the very first mount. A filter box, a header sort or a page click all
  set `isFetching` without ever setting `isLoading` again — `loading={query.isLoading}`
  showed rows aging silently on a slow connection with no sign a request was in
  flight (measured: 700ms latency, six checks 150ms apart, no overlay). MUI's
  own `GridLoadingOverlay` draws a `linear-progress` bar over the existing rows
  when `loading` is `true` and the grid already has rows.

  **The same window locks what would ask again - paging and sorting, never
  the filter boxes.** Two requests for the same screen in flight at once
  race, and the one that lands second silently wins the footer's total and
  the rows shown. So `ServerDataGrid` carries
  `slotProps={{ basePagination: { disabled: loading } }}` (`pagination` is the
  wrong slot key; `GridPagination` reads `basePagination`) and
  `disableColumnSorting={loading}` (the sort affordance disappears rather than
  sitting there disabled-looking but clickable). The filter boxes stay live:
  the fetch fires 300ms after the last keystroke, and a box that locked then
  cut the word still being typed (measured: `밀가` sent, `루` dropped). The
  race a locked box would close is closed by the query key instead - a newer
  key supersedes the older answer - so `ListFilters` takes no `disabled`.

  **A dialog's table is the same contract.** `ServerPagedTable` - the runs
  log, a material's products - draws its own `LinearProgress` and locks its
  `TablePagination` from one `loading` prop, and every caller passes the
  query's `isFetching`. Measured before the prop existed: the runs dialog's
  next-page button stayed live with no bar while a page was in flight - the
  hook watched only the grid, and the dialog table was a second surface
  with the same failure. Verified by throttling the network to 900ms and
  reading each control's state mid-flight.

- `useQueryErrorToast` — a failed page otherwise renders as an empty list, the
  one state a user cannot tell from success
- `emptyTitle` — the empty state needs a sentence

### Sorting

**The header sorts the collection, on the server.** `useDataGridState` keeps
the one sorted column and sends it as `sort` and `order`; a sort change lands
on page one, because page 4 of a list sorted one way is not page 4 of it sorted
the other. `ServerDataGrid` runs `sortingMode="server"`, so the grid never
sorts the loaded page itself - measured before the rule: every list sorted its
ten rows on a header click and called it the collection, with every gate
green, because the grid, the router and the hook were each correct about a
sort that reached nothing.

The columns a grid may sort are the router's to close: `<Domain>SortQuery` in
`app/dependencies/query.py` is a `Literal` of them (rule://backend-router-params).
A column the server does not sort - the password mask, a scheduler state, a
count of children - says `sortable: false`, or its header's first click answers
422. `check-frontend-screens` demands the wiring and holds every `sized(...)`
column not marked `sortable: false` to the Literal.

### Filtering

**One box per column, named as the query parameter.** `FILTER_FIELDS` is the
list of parameter names (`['username', 'email']`), and the boxes are built from
it — so a box, its label and what it sends cannot drift apart, and a name the
router does not read fails `check-frontend-types` instead of filtering nothing.

**The label is looked up, never branched.** `FILTER_LABEL_KEYS` maps every
field to its locale key and the box reads `t(FILTER_LABEL_KEYS[field])`. A
ternary on the field name (`field === 'code' ? t('filter.code') : t(...)`) is
right for two fields and silently wrong for the third: the else branch labels
whatever is added next. `check-frontend-screens` demands the map, one key per
`FILTER_FIELDS` entry, and the lookup in the `label:`.

**One query parameter, one control.** A list narrows through a single params
object, so the controls on the screen *are* the answer to "why am I seeing these
rows". Drive one parameter from two of them and the screen holds two answers for
one column while neither control shows the other's value.

Measured: a tab strip was built over `record_kind` while that column still had its
filter box. Clicking 회수·판매중지 and then typing 검사부적합 into the box left the page
narrowed by the box, the strip highlighting the other kind, and nothing on screen
saying which had won — with every gate green, because the field was in
`FILTER_FIELDS`, the parameter reached the repository and the types matched.

The check is structural rather than about tabs: a parameter written **literally**
into the screen's params object may not also be in `FILTER_FIELDS`, and
`FILTER_FIELDS` may not name a column twice. A spread (`...filters.params`) is
another control's contribution and carries no literal key, so it is not a second
control over itself. Both shapes were planted and both fire.

So a control that *replaces* a box — a tab strip, a segmented switch — removes
that field from `FILTER_FIELDS` in the same edit. Adding one beside the box is
the defect this refuses.

A single keyword box over several columns is not the standard: it cannot say
which column matched, and the reader who wants "the account whose *email*
contains probe" has to hope. The backend follows the same shape —
`TextFilterQuery` per column, `ilike`, AND between them — and applies every
filter to the **count** as well as the page, or the footer describes a
collection the grid is no longer showing.

An empty box is an omitted parameter, never `field=`: the parameter declares
`min_length=1`, so the empty string is a 422 on a screen the reader thinks is
unfiltered.

`useListFilters` owns the debounce (300ms — every keystroke is a query key) and
the page reset (a filter matching three rows while the grid sits on page 4
answers an empty page, which reads as "no results").

#### Select filters

A filterable column is one of two kinds, and **the column decides**, not the
screen:

| Column holds | Box | Router matches | Value comes from |
|---|---|---|---|
| free text (a code, a name, an alias list) | search field | contains (`ilike`) | the reader types it |
| a closed vocabulary (a class, a status) | **select** | **equals** | a `facets` endpoint: the column's own distinct values |

A field becomes a select by carrying `options` (`ListFilters`), and the select
is an `Autocomplete`: **the reader types to narrow it**. The vocabularies are
the columns' own values and some are long - hundreds of 식품유형 on the item
report list, dozens of 상태 on the raw material one - so a plain
dropdown makes a reader who knows their value hunt for it. Typing filters the
options by contains, and what the box sends is still one of them, so the
router's equals holds; clearing is "all", and `allLabel` is what the empty box
says. Verified end to end on screen: typing narrows the options to one,
picking it answers exactly the SQL count for that value, and the clear button
puts the whole table back. Both popups are bounded by `SELECT_MENU_MAX_HEIGHT`
(rule://frontend-design), so a long vocabulary scrolls under its box instead of
taking the viewport. The options are **fetched, never typed into the screen**: the portal owns those vocabularies and
the sync brings a new value the night it appears, so a list written into the
component would offer yesterday's choices. The screen names the select columns
in `SELECT_FIELDS`, reads `use<Domain><Table>Facets()`, and passes each column's
list; the first entry is "all" with the empty value, which is the same empty
`useListFilters` already treats as "no filter" - a select and a text box clear
the same way.

Why equals: the value was picked from the column's own list, so a contains
match would only widen it - `식물` is a prefix of `식물성유지`, and a reader who
picked the first did not ask for the second. The backend spells the two kinds as
`TextFilterQuery` and `ExactFilterQuery` on the router, and applies them from one
filter model so the page and its total narrow together.

Verified against SQL: a class + status pair picked on the screen answers the
same count the equivalent SQL does.

**A vocabulary the schema itself closes is the one exception.** `use_yn` is
`Literal["Y", "N"]` on the server, so its two values are the contract's, not a
read: the screen names that column (`const CODE_FIELD = 'use_yn'`), offers the
type's constant (`USE_FLAGS`), and owes `optionLabel` - a code is not a word a
reader knows, and `Y` prints as `Y` in every language. Every other select
column's values are its own rows', which only `facets` has.

**Machine-checked** (`check-frontend-screens`): an `options:` expression that
contains a quoted array literal fails (vocabularies are fetched); a select
column not named as a `CODE_FIELD` must take its options from `facets.data`,
and a screen whose options name `facets.data` must call
`use<Domain><Table>Facets()`, and `ListFilters` must render `Autocomplete` rather
than a plain `TextField select` - measured by planting each: a select whose
options came from nothing, and one reading a `facets` that was never fetched,
both passed every gate before these; every `SELECT_FIELDS` name must be
`ExactFilterQuery` and every other `FILTER_FIELDS` name `TextFilterQuery` in
`backend/app/routers/<domain>.py` (the screen's kind and the router's match
agree); a `CASCADE` declaration owes `setInput(CASCADE.child, '')`; and
`ListCardHead`'s filter boxes never leave the row (a wrapping flex row or an
`auto-fit` grid - the property, not the spelling).

**Machine-checked on the server too** (`check-backend-router-params`): a list
endpoint that declares `ExactFilterQuery` owes a `GET <prefix>/facets`, and
that route's response model owes a field per such column - a whole-value match
is a value picked from a list, and the list is what the route is for.

**Cascading selects.** When one closed vocabulary is a child of another (the
medium class under the large class - measured: 1 to 8 children per parent
against 30 in all, one value shared by two parents), the `facets` endpoint
answers the child twice: flat, and grouped by parent. The screen declares the
pair (`CASCADE = { parent, child }`), hands the child select the parent's group
once a parent is chosen and the flat list otherwise, and **clears a child the
new parent does not have** - a filter that can match nothing must not stand.
The rule lives beside the field list, not in `ListFilters`: which field narrows
which is domain knowledge, and the component renders what it is handed.
Measured: `건강기능식품(C코드)` → 3 children, `개별인정` → 976; switching the
parent to `위생용품(E코드)` cleared the child and answered 1,118.

The filter boxes are a grid of equal cells (`ListCardHead`, `repeat(auto-fit,
minmax(FILTER_MIN, 1fr))`), one column below `sm`: as many per row as fit, and
the cells stretch to the card's edge. Fixed widths failed twice - six boxes at
1400px ran past the card and the last select sat at x=1530, off-screen (a
filter nobody can reach is a filter that does not exist), and at 900px they
folded into 3+3 with a ragged right edge and the reset stranded beside the gap.
The reset lives with the refresh in the head's action row, not among the boxes:
it acts on the whole head, and as a seventh cell it fell alone onto a third row
whenever the boxes filled their rows exactly.

### Editing In Place

A list may edit rows in the grid instead of in a dialog, and should when the
editable columns *are* the row: a dialog for three scalars asks for what the row
already shows. `ServerDataGrid` takes the row-edit props; `editMode` is fixed to
`row` there, because cell-at-a-time editing would send one PUT per cell to an
endpoint that takes the whole resource.

`useRowEditor` owns the mechanism — the modes map, `startEdit`/`commitEdit`/
`cancelEdit`, the deferred caret move, and the `reported` flag that stops a
refused save being explained twice. Three screens carried it and 24 of their 26
row-edit lines were byte-identical, which is a mechanism, not a decision.
A screen that edits rows without handing its refusal to that hook fails
`check-frontend-screens`.

What the screen still owns:

- `problemOf` and `refusal` — what *this* domain refuses, in its own words: a
  password is required on a draft row and never on a saved one
- `processRowUpdate` — one mutation, returning the server's row so the grid shows
  the new `version`, wrapped in `editor.guardRowUpdate`
- `apiRef` — created in the screen and handed to both the hook and the grid, so
  the pending values the hook reads are the ones the grid is showing
- `preProcessEditCellProps` — `problemOf` again, so a red cell and the refused
  save can never disagree
- `onRefused`/`onCommitted`/`onCancelled` when the screen keeps more than modes:
  the user list marks refused rows, and drops a cancelled draft instead of
  reverting it to a version no endpoint ever stored

### Creating In The Row

**Is every field of the create an editable column?** That is the whole criterion,
and it is machine-checked (`check-frontend-domain`) by comparing
`<Domain>CreateRequest` in `types/<domain>.ts` against the list's columns that
carry `editable: true`:

| Domain | Create fields | Verdict |
|---|---|---|
| `user` | `username`, `email`, `password` — all editable columns | the row is the form: `+` opens a draft row, no `UserFormDialog` exists |
| `batch` | includes `description`, a multiline value that is no column | the dialog creates; the row does not |
| `integration` | includes nested `secrets`, and `code` is read-only | the dialog creates; the row edits its three scalars |

Both directions fail: a domain whose whole create is editable columns may not
keep a dialog, and a list may not carry a draft row for a record with a field no
cell can hold. Before the check the criterion was prose, so a domain of three
scalars could keep a dialog and nothing would say so.

A draft is dropped in the update **after** the one that ends its edit
(`queueMicrotask`). Removed in the same update, the grid was still stopping an
editor whose row had vanished and fell back to committing it: cancelling a new
row POSTed the empty draft and answered 422 (measured, twice — the second time
by deriving the row's presence from its mode, which is the same update).

`ServerDataGrid` also prevents MUI's default `rowFocusOut` commit: a row saves
when someone says save, never when focus leaves it. Without it, clicking the
row's own cancel first blurred the cell and sent the write the click was there to
abort.

### Refusing A Save

A grid's own answer to an invalid row is to refuse the commit and stay open —
**silently**, so the save button reads as broken. A screen that edits in the grid
therefore holds `apiRef` and, on save:

1. reads the pending values (`getRowWithUpdatedValues`) — they live in the grid's
   edit state, not in `rows`;
2. judges them with the **same function** the cells' `preProcessEditCellProps`
   use, so a red cell can never be red for a reason the message does not name;
3. toasts one sentence and puts the caret in the offending cell
   (`setCellFocus`, deferred — the clicked button takes focus back on its own
   mouse event);
4. does the same inside `processRowUpdate`, because Enter commits through the
   grid and a rule enforced on the button alone lets the keyboard past it.

The sentence is **one sentence**, carried by the rule itself
(`{ key: 'validation.password_min', count: 8 }`), never a label and a code joined
with a colon: Korean joins them with a different particle per field, so
`비밀번호: 8자 이상 입력하세요` reads as two fragments where the locale can write
`비밀번호는 8자 이상이어야 합니다`.

Nothing is said while typing. A cell turns red once it has been typed into or
once someone has claimed the row is finished — an empty new row is not a row of
mistakes.

Every intent a row can serve is a button in its last column — detail, edit,
delete, and the save/cancel pair while editing — built by `rowActionsColumn`,
which returns MUI's own `type: 'actions'` column so the grid owns focus and
`tabIndex` for the buttons.

**A row may also be a door, and the door is guarded in the grid.** The rule used
to be that an editable list takes no `onRowClick` at all, which put the decision
in the wrong place: the collision is MUI's, and it is two collisions. A click in
the actions cell is reported as a row click as well, so a door would open a
dialog on the way to `삭제`; and a cell double-click starts an editor whose first
click had already opened that dialog. `ServerDataGrid` answers both once — a row
in edit mode has no door, a click inside `[data-field="actions"]` belongs to its
button, and double-click editing is off wherever a door is set, so editing
starts at the row's own button. `check-frontend-screens` reads those three
guards on the grid, not the ban on each screen.

**One intent, one control.** A door replaces the button it duplicates rather
than sitting beside it: `BatchList`'s row opens its run log, and the `실행 이력`
button is gone — the reader finds the row without looking for an icon, and the
actions column dropped from five verbs to four, giving the width back to the
data columns. What keeps its button is what a row click cannot mean: run, stop,
edit, delete.

**`count` is the widest branch, and it is the column's width.** The number is not
documentation of the array beside it: `rowActionColumnWidth(count)` is what the
column asks the grid for. Declare fewer than a row can draw and the last buttons
are clipped — a stop button nobody can reach, reported by no type and no test,
because the array is built per row at runtime. Declare more and the reserved
width comes off the data columns, on a card that was already tight enough to
cost `BatchList` its `description` column.

A **maximum**, never an equality with one array: a row that edits in place
returns save/cancel while editing and view/edit/delete otherwise, so
`IntegrationList` declares `3` while one of its branches holds `2`. The equality
form was written first and fired on that screen — the width a column keeps in
every row is the width its widest row needs. `count: 2` there matched a real
branch exactly and was still wrong, which is why the check compares the maximum.

A column the API cannot change stays read-only. `code` has no rename, so an
editable code column would accept a value the server ignores.

## Form Dialog

- `useForm` + a resolver (`yupResolver`) — the schema is the only validator
- `FormProvider` + `RHF*` field wrappers — a raw `<TextField value onChange>`
  inside a form keeps a second copy of the value, so the resolver validates one
  string and the user sees another
- `methods.reset(...)` on open — the dialog stays mounted between rows, so
  without it the second row edited shows the first row's values
- **no `useState` for field values**
- one dialog serves create and edit unless the list edits in place; then the
  dialog serves create, and the lengths it declares are exported for the grid

## Record Dialog — the `/integration` standard

`sections/integration/` is the worked example every new domain copies. The shape,
top to bottom:

| Layer | File | Owns |
|---|---|---|
| List | `<Domain>List.tsx` | `ServerDataGrid`, inline row edit, delete confirm |
| Dialog | `<Domain>DetailDialog.tsx` | header, tab strip, **panel mode**, **paging state** |
| Tab | `detail/<Domain><Child>Tab.tsx` | columns + cells, through `PagedTableSection` |
| Panel | `<Domain><Child>Panel.tsx` | one record read **and** edited, through `PanelStrip` |
| Delete | `<Domain><Child>DeletePanel.tsx` | the cost, through `RecordDeletePanel` |

`check-frontend-screens` enforces it through `lib/frontend-record-dialog.ts`. Every
rule is checked by **position or ownership**, never by whether a file mentions a
name — a grep passes on a file that names the right component in a comment while
rendering the wrong one. Every rule is also **conditional on the domain having the
thing it governs**: a dialog owns the page only when one of its tabs draws a paged
collection, a tab must use the shared frame only when it draws a table at all. A
requirement invented out of the exemplar's shape is how a standard becomes a
costume — measured twice, when the first version reported three list screens for
their own column widths and would have reported a scalar-only tab for having no
table.

Each rule was proven to fire by planting the violation, and the whole set was run
against a synthetic second domain (`sections/vendor/`): the conforming shape
passes, a scalar-only domain with no table and no paging passes untouched, and
every violation fires.

**One modal, then panels.** A confirm dialog stacked on a detail dialog hides the
record it asks about, and a third layer over a half-filled form has nowhere to go
back to. A panel *replaces* the dialog body while the header stays, and leaving is
drawn by the panel's strip.

**Leaving is raised above the identity row, because it is navigation and not a
verb on the record.** The strip's second line holds what is being acted on and the
verbs acting on it; `뒤로`/`취소` sits on the line above, drawn from `onBack`. Inline
it was the first of five things in one 900px row — `뒤로 GET
search-product-classification /api/{…} 실행` — the row a reader scans to see what
the record *is*. A control among the strip's children is refused: verbs go through
`actions`, leaving through `onBack`.

**The identity row is one line, and exactly one child absorbs what is left.**
Every child keeps the width it asked for, and the child that already declares it
truncates (`noWrap`) takes the remainder — so two `noWrap` children are refused,
because two long values then shrink against each other and neither is readable.
Measured without the rule: each child could shrink to its own min-content, so
`search-product-classification` broke at its hyphens into two lines, doubling the
row and squeezing `실행` until its two glyphs stacked into a column.

**One run has one ending, and one place that shows it.** A panel holds the whole
outcome in one state value and renders one result section — the status badge and
the payload blocks — whether the call succeeded or the provider refused. The alert
under the strip carries the *reason* (`외부 API 호출이 실패했습니다`), never the
response. Measured when they were split: the failure grew its own
status-plus-payload block above the inputs that produced it, and a failed re-run
left the previous success on screen underneath the new error, because the success
lived in the mutation's `data` and the failure in a second state.
`check-frontend-screens` refuses a panel that renders a mutation hook's `.data`.

**A tab is a pure presenter**: it takes what it was handed and queries nothing. A
tab that fetches refetches on every tab switch and can show a different version
of the row than its siblings.

**One exception, and it is declared, not argued**: an **execution log**
(`EXECUTION_LOG` in `hooks/lib/hook-product-areas.ts`, rule://product-areas) is not
part of the entity — a row per call for ever, server-paged, written by whatever
exercised the configuration — so it cannot arrive as a prop from the entity read
its siblings share, and there is no second version of those rows to disagree
with. `IntegrationCallsTab` reads `useIntegrationCallList` for that reason.
`check-frontend-screens` permits exactly the declared log hooks: a tab that also
imports its entity's own hook still fails.

**A record is addressed by the key the server keeps unique**, never by the object
— in the exemplar an operation by `code` and a credential by `name`. `PUT`
replaces the whole nested array, so a held object is a stale row with a new id
behind it. The mode resolves its record on every render, and a mode whose key no
longer resolves falls back to the tab list.

**The dialog owns what has the dialog's lifetime**: which tab shows, which panel
replaced the body, and where each table is paged to. Paging cannot live in the
tab — opening a record unmounts it, and the reader returns from the record they
just edited to page 1 (measured: deleting the last credential on page 2 of 12
landed back on `1–10`). The close transition resets all three.

**One record has one surface.** Reading renders text, editing turns the same rows
into inputs, and the pinned strip carries both modes' verbs. Two screens for one
record — a read-only detail panel plus an edit form — is the shape this replaced;
they differed only in which mode the door landed in. Editing is panel state, not
a route, so pressing edit keeps the record scrolled where it was; cancelling
restores the form from the record it was given.

**A read is text, never a disabled input.** WCAG exempts disabled controls from
contrast (`1.4.3`), screen readers skip them, Tab skips them. A read renders
`DetailField`; a state renders the `Label` badge the tables use; a value that
cannot change but must stay legible carries `readOnly` plus `aria-readonly`.
`RecordFields` (`ScalarField` / `ChoiceField` / `NumberField`) is that switch, in
one place, because two panels wrote it separately and drifted.

**A row carries one door, not two**: open and delete. A pencil beside the eye was
a second route into the same panel, differing only in the mode it landed in —
"edit" is the button inside the record.

**A value that is a sentence is read whole; a table clips.** A table earns its
place when every cell is a word or a number and the row is the unit of reading.
When the value *is* the content - a clause of the Food Code, a condition and a
sentence and a judgement per row - a table with `ClippedText` hides exactly
what the reader opened the record for (measured: the standards table showed
`제품은 고유의 형태, 색택을 가…` and `…` on every row, and its heading
column clipped at the three levels every row shares). Such a value is an
outline: grouped under the structure the source has (the Code's headings, in
the source's order), the shared prefix printed once, each entry printed whole
and wrapped, folded by group past a measured size (`FOLD_OVER`), no paging - an
outline is read, not browsed. Decide by the value's measured length, not by
whether a table was easier to write.

**A row's key is the row's identity, never its words.** `rowKey` is what
React keeps a row's DOM by; built from rendered values (`type:item:clause`) it
collides the moment the server writes two rows alike - which the Food Code
does (가공식품 lists 금속성이물 twice under one heading with the same clause and
detail) - and a collided key keeps a stale row on every page after the first
(measured: nineteen rows on a page of ten). So every `rowKey` reads
`.id`, a prefix beside it allowed; `check-frontend-screens` refuses one that
does not, following a named key function to its body. The other half is the
server's: every row read carries `id: UUID` beside `version` (`backend-domain`),
so a nested read never leaves the client with only the row's words.

**Every table pages, and the footer shows whenever there are rows.** Hiding it
under the first page size reads as an inconsistency: a reader who sees the total
on one record and not the next cannot tell whether the second is short or
broken. One row renders `1–1 / 전체 1` with both arrows disabled. The page number
is clamped, never trusted — 11 rows keeps page 2 showing `11–11`, 10 rows falls
back to page 1, because a table rendering nothing under `11–20 of 10` reads as a
failed load. Footer wording comes from `usePaginationLabels`, which the list grid
reads too: MUI core has no locale bundle here and MUI X's koKR is half-translated
(`페이지 당 행:` beside `1–2 of 2`).

**Clipping is allowed; clipping without a visible tooltip is not.** These tables
clip on purpose — `text-overflow: ellipsis` is what keeps a row at one height and
a column at its declared share — so a cell that prints a value renders
`ClippedText`, and `ServerDataGrid` injects it for every text column it is given.
Measured before it did: `mfds-food-safety-korea` read as `mfds-food-safet...` and
the rest of the value existed nowhere on screen. Header labels are values too: a
label clipped at 9% of the width is as unreadable as a clipped row.

**The native `title` attribute does not count.** It was the first fix and it was
not one: the browser draws that tooltip in its own chrome, so nothing in the DOM
proves it appeared — reported from the screen, it did not. `ClippedText` renders
MUI's `Tooltip`, which mounts a real `[role=tooltip]` node, so a real-pointer
hover is measurable.

**The bubble appears 12px above the cursor and then stays put** (`placement="top"`
over a zero-size anchor at the entry point; measured `gapAboveCursor: 12`,
`centredOnCursor: 0`, and `movedWithPointer: false` after a 45px pointer move).
Three attempts, all measured: anchored to the element it landed on top of the
table header and read as a label for something else (41px from the pointer);
`followCursor` closed the distance and cost the stillness, which is worse — text
that slides while the eye reads it cannot be read; under the value it was still
but nowhere near the hand on a wide column. It attaches **only while the text
overflows**, re-measured on resize, because a tooltip repeating a value already
fully readable is noise on every row and trains the reader to ignore the one that
matters.

A cell whose content is a component is exempt, because it owns its own hover
story — a `Label` badge says one word that never clips, `RowActionButtons` names
each button.

**A panel's alert goes under its strip, never at the end of its body.** The
mapping warning and the rejected-save error are the reason the pinned save is
dead, and a reason below the fold is a reason nobody reads: 22 response fields put
the warning off-screen while the disabled button stayed in view. A delete panel's
*cost* sentence is the exception and stays with the record summary, because it
describes the record rather than a blocked action.

**Helper text is for a rule that is broken, not for a rule that exists**, and the
same holds one layer up: a permanent `Alert severity="info"` is not a place to
keep a fact. A value's *shape* goes in the `placeholder`, which shows while the
field is empty and leaves when it is not. `값은 저장 후 다시 읽을 수 없습니다`
pinned above a one-row table was answering a question nobody had asked; it now
sits under the masked value, where someone looks for a key and does not find it.

**A write-only value is a mask, never a rendering.** Reading a credential shows a
fixed mask; editing starts with an **empty** input whose placeholder is that mask
plus a line saying an empty box keeps the stored key — which is what the
contract's optional `value` means. Prefilling the input with the mask would save
the mask as the key. The name is the address, so it is `readOnly` while editing.

**In the exemplar's field editor: `PATH` is substituted, `PATH_QUERY` is appended —
never gate them together.**
The backend joins `PATH_QUERY` fields with `&` and hangs them off the end of the
path, so such a field carries a wire name and no placeholder. Treating both as
"path-carried" reported `REQUEST #6: {last_updated_from}` on a correctly seeded
operation and left save dead. Only `PLACEHOLDER_LOCATIONS` (`['PATH']`) drives
the template checks; order-in-the-URL is the one thing both share. The converse
is checked too: a `{name}` in the template that no `PATH` row declares is an
issue, because no row owns a placeholder that has no row.

## Run History — a log opened from a row

Not machine-checked: one domain has this shape so far, and a template written
from a single instance is a costume. What follows is the decision record
`BatchRunsDialog` left, for the second one to copy or depart from deliberately.

**Two `ServerPagedTable`s, not `ServerDataGrid`.** That template owns a page's
worth of chrome — density, column visibility, a toolbar — and its state is the
screen's. Two of them nested in a dialog that closes would carry all of it for a
log nobody sorts.

**Both levels page as requests, and their footers may disagree.** A run log grows
by one row per night forever and a resumable sync writes a step per window, so
neither collection can be fetched whole and sliced. Paging the runs must not lose
the steps of the run already open.

**Selecting a parent row toggles; choosing a different one resets the child to
page 1.** The second page of the previous run's windows is not a page of these.
Closing resets the selection and both page states.

**The child's empty state is a sentence about the domain, not "no data".**
`기록된 단위가 없습니다 — 수동 CLI 실행은 단위를 남기지 않습니다` tells the reader the
run succeeded and wrote nothing, which is a different fact from a failed load.

**The status vocabulary is the backend's `CHECK` constraint, rendered through
`Label`.** One map from status to colour, keyed by the union (never `string`), so
a sixth ending added to the constraint fails the build here instead of rendering
as a grey badge nobody reads.

## Dashboard

Every widget owns its query, its loading state and its failure. There is no
shared "dashboard is loading" flag — one failing widget must not blank the page.
A card renders a number only when it has one; `0` while fetching is a false fact.

## Confirming A Delete

`ConfirmDialog` is the one question every delete goes through, and it wears the
app's dialog head (`FormDialogHeader`, `tone="error"`): one icon size, one title
weight, one close button, one dashed rule. A bare `DialogTitle` here was the
app's only plain heading, larger than the titles beside it.

**The body is one sentence**, the domain's own
(`messages.delete_confirm`), naming the row *and* what deleting costs. It was
two — the row, then "이 작업은 되돌릴 수 없습니다" as a caption — and the split
implied two facts of different weight where there is one. A caption is for
something the reader may skip; the cost of a delete is not that. The title says
the verb once, so the body never repeats it.

`xs` + `fullWidth`, so the question is the same width wherever it is asked.

## Reporting Failure

One vocabulary, two entry points, and both of them end in a toast:

| Failure | Reported by | Retry |
|---|---|---|
| A read (`query.isError`) | `useQueryErrorToast(query, tCommon('messages.load_failed'))` | the toolbar's refresh |
| A write (`mutateAsync`) | `applyServerError` / `serverErrorMessage` / `useToast` | the user resubmits |

A failed read used to draw an inline `<Alert>` above the table. That put a banner
and a toast on one screen for the same idea, carried a second retry beside the
toolbar's refresh, and inside a dialog it *replaced* the table it was describing,
so the reader lost the paging controls that would have re-requested the page.
`useQueryErrorToast` takes the query, not its `isError` flag: the episode is
keyed by `errorUpdatedAt`, so every failed fetch is answered exactly once and a
re-render is answered not at all. Keyed on the flag instead, a retry against a
dead API drew a spinner and nothing else — `isError` was already true.

No screen renders `messages.load_failed` itself, and no `isError` branch belongs
in JSX — `check-frontend-screens` fails on both.

## Review Judgement (not machine-checked)

- Whether a copied screen should have diverged as much as it did. The template
  is checked; taste in departing from it is not.
- Whether a list's columns, an empty sentence or a confirm body actually say
  something. `emptyTitle` is required to exist, never to be informative.
- Whether a dialog should have been a page. A 12-field form in an `sm` dialog
  passes every check and is still the wrong container.
- `PageHeader` is required only on pages routed under `DashboardLayout` — the
  set is read from the route table, so login and the catch-all are exempt by
  construction rather than by a name list.

## Never Do These

- Render `DataGrid` outside `components/data-grid/ServerDataGrid.tsx`
- Ship a list screen with no `useQueryErrorToast` or no empty sentence
- Build a list head by hand instead of `ListCardHead`, or give it a density
  control or a labelled add button
- Filter with one keyword box over several columns, or with boxes whose names
  are not the router's query parameters
- Refuse a save without saying why, or say why with a label and a code joined by
  a colon
- Pass `cannot_undo` into `ConfirmDialog` — the sentence the domain writes says
  it
- Report a failed read in the body — no `<Alert>`, no `isError` branch in JSX
- Hold form field state in `useState`
- Skip `methods.reset` in a dialog that is reused across rows
- Fetch inside a detail tab (other than its domain's declared execution log) or
  inside a page component
- Await a mutation without reporting failure — route it through
  `applyServerError` (`lib/api/formErrors.ts`), which translates the server's
  `code` via `errors.<code>` and puts the sentence on the field that owns it,
  through `serverErrorMessage` when the failure belongs where the result would
  go (the operation console), or through `useToast` when no field does
- Add a filter or sort control the backend has no parameter for
