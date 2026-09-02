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
| Form dialog | `sections/<domain>/<Domain>FormDialog.tsx` | `sections/user/UserFormDialog.tsx` |
| Detail + tabs | `sections/<domain>/<Domain>DetailDialog.tsx` + `detail/*Tab.tsx` | `sections/integration/` |
| Dashboard | `sections/dashboard/DashboardView.tsx` | independent widgets |
| Auth | `sections/auth/LoginForm.tsx` | session, not a resource |

## List Screen

Four hooks, in this order, and nothing else holds state:

```tsx
const grid = useDataGridState()
const query = use<Domain>List(grid.params)
const rows = query.data?.items ?? []
const rowCount = query.data?.total ?? 0
const dialog = useCrudDialog<Domain>()
const toast = useToast()
```

Required parts:

- `ServerDataGrid` — never MUI's `DataGrid` directly
- an `isError` branch with a retry action — a failed page otherwise renders as an
  empty list, the one state a user cannot tell from success
- `emptyTitle` — the empty state needs a sentence
- the create button lives in the card toolbar, so the screen owns its own dialog
  state and no parent has to pass an "open" flag down

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
- `preProcessEditCellProps` — the lengths and patterns the create form declares,
  read from it rather than retyped, so an invalid cell never becomes a 422

Every intent a row can serve is a button in its last column — detail, edit,
delete, and the save/cancel pair while editing — built by `rowActionsColumn`,
which returns MUI's own `type: 'actions'` column so the grid owns focus and
`tabIndex` for the buttons. A grid has no row click: `ServerDataGrid` does not
take `onRowClick`, because a row that opens a record when clicked cannot also be
a row a user types into.

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

## Dashboard

Every widget owns its query, its loading state and its failure. There is no
shared "dashboard is loading" flag — one failing widget must not blank the page.
A card renders a number only when it has one; `0` while fetching is a false fact.

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
- Ship a list screen with no error branch or no empty sentence
- Hold form field state in `useState`
- Skip `methods.reset` in a dialog that is reused across rows
- Fetch inside a detail tab or inside a page component
- Await a mutation without reporting failure — route it through
  `applyServerError` (`lib/api/formErrors.ts`), which translates the server's
  `code` via `errors.<code>` and puts the sentence on the field that owns it,
  through `serverErrorMessage` when the failure belongs where the result would
  go (the operation console), or through `useToast` when no field does
- Add a filter or sort control the backend has no parameter for
