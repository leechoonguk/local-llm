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

## Screen Types

| Type | File | Exemplar |
|---|---|---|
| List + CRUD | `sections/<domain>/<Domain>List.tsx` | `sections/user/UserList.tsx` |
| Ledger list (read-only) | `sections/<domain>/<Domain><Table>LedgerList.tsx` | `sections/food/FoodRawMaterialLedgerList.tsx` |
| Form dialog | `sections/<domain>/<Domain>FormDialog.tsx` | `sections/user/UserFormDialog.tsx` |
| Detail + tabs | `sections/<domain>/<Domain>DetailDialog.tsx` + `detail/*Tab.tsx` | `sections/integration/` |
| Run history | `sections/<domain>/<Domain>RunsDialog.tsx` | `sections/batch/BatchRunsDialog.tsx` |
| Dashboard | `sections/dashboard/DashboardView.tsx` | independent widgets |
| Auth | `sections/auth/LoginForm.tsx` | session, not a resource |

## Column Width

Every grid column has a **floor** and, if it may grow, a **share**: `width`, or
`flex` with `minWidth`. MUI's default is 100px with no floor, which clipped
14-character codes and `식품원료(A코드)` on the raw material ledger; `flex` on
two columns alone piled a 1920px screen's spare width into those two while the
rest stayed clipped. The floor is the width at which the column's widest
measured value stops clipping; the share is how much of a reader's attention the
column earns. A screen with many columns keeps them in one table
(`COLUMN = { field: { floor, share } }`) and spreads it with `sized(field)`,
so the numbers sit together and every column is sized by construction.

`check-frontend-screens` fails a column literal with neither `width` nor
`flex`+`minWidth`; a `...sized(...)` spread is exempt because its table's type
requires both.

## Ledger List

The list template with its write half removed. A ledger is a table a nightly
provider job replaces with a whole pass of its feed (a `Feed` of
`backend/app/batch/sync_<provider>_ledgers.py`), so a row typed on this screen
would be overwritten by morning - and the backend has no verb to accept it
(`backend-domain.md`, "Ledger Domains Are Read-Only Over HTTP").

Four hooks, in this order, and nothing else holds state:

```tsx
const grid = useDataGridState()
const filters = useListFilters(FILTER_FIELDS, grid.resetPage)
const query = use<Domain><Table>List({ ...grid.params, ...filters.params })
useQueryErrorToast(query, tCommon('messages.load_failed'))
```

What it keeps: `ListCardHead` (without `add`), `ListFilters`, `ServerDataGrid`,
`emptyTitle`, the toolbar refresh. What it refuses: `useCrudDialog`, `useToast`,
`rowActionsColumn`, `processRowUpdate`, any mutation, any form dialog. Every
column of the ledger is a grid column - the column selector is the detail view,
so there is no detail dialog and no GET-by-id.

**The suffix is a claim the backend must back.** `check-frontend-screens` holds
`<Domain><Table>LedgerList.tsx` to a feed whose service is
`app/services/<domain>/<table>.py` (`hooks/lib/backend-ledger-feeds.ts`); a
table nothing syncs is edited by people and
gets the CRUD template. Measured before the rule: the CRUD check demanded
`useCrudDialog` on the raw material screen, and the only way to satisfy it was a
dialog that edited rows the next sync would erase.

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
- `ServerDataGrid` — never MUI's `DataGrid` directly
- `useQueryErrorToast` — a failed page otherwise renders as an empty list, the
  one state a user cannot tell from success
- `emptyTitle` — the empty state needs a sentence

### Filtering

**One box per column, named as the query parameter.** `FILTER_FIELDS` is the
list of parameter names (`['username', 'email']`), and the boxes are built from
it — so a box, its label and what it sends cannot drift apart, and a name the
router does not read fails `check-frontend-types` instead of filtering nothing.

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

A field becomes a select by carrying `options` (`ListFilters`). The options are
**fetched, never typed into the screen**: the portal owns those vocabularies and
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

Measured on the raw material ledger (2026-09-05): 7 large classes, 30 medium
classes, 85 status names; `식품첨가물(B코드)` + status `-` answered 6,722 on the
screen and 6,722 in SQL.

**Machine-checked** (`check-frontend-screens`): an `options:` expression that
contains a quoted array literal fails (vocabularies are fetched); every
`SELECT_FIELDS` name must be `ExactFilterQuery` and every other `FILTER_FIELDS`
name `TextFilterQuery` in `backend/app/routers/<domain>.py` (the screen's kind
and the router's match agree); a `CASCADE` declaration owes
`setInput(CASCADE.child, '')`; and `ListCardHead`'s filter row carries
`flexWrap="wrap"`.

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

The filter row wraps (`ListCardHead`): six boxes at 1400px ran past the card and
the last select sat at x=1530, off-screen - a filter nobody can reach is a
filter that does not exist.

### Editing In Place

A list may edit rows in the grid instead of in a dialog, and should when the
editable columns *are* the row: a dialog for three scalars asks for what the row
already shows. `ServerDataGrid` takes the row-edit props; `editMode` is fixed to
`row` there, because cell-at-a-time editing would send one PUT per cell to an
endpoint that takes the whole resource.

What the screen still owns:

- `rowModesModel` — controlled, so an action can start and stop the edit
- `processRowUpdate` — one mutation, returning the server's row so the grid shows
  the new `version`; throwing is what makes the grid revert and stay open
- `onProcessRowUpdateError` — the failure needs the same sentence a dialog gave
- `apiRef` + a **refusal**: see below
- `preProcessEditCellProps` — the same rule the refusal states in words

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
`tabIndex` for the buttons. A grid has no row click: `ServerDataGrid` does not
take `onRowClick`, because a row that opens a record when clicked cannot also be
a row a user types into.

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
- Fetch inside a detail tab or inside a page component
- Await a mutation without reporting failure — route it through
  `applyServerError` (`lib/api/formErrors.ts`), which translates the server's
  `code` via `errors.<code>` and puts the sentence on the field that owns it,
  through `serverErrorMessage` when the failure belongs where the result would
  go (the operation console), or through `useToast` when no field does
- Add a filter or sort control the backend has no parameter for
