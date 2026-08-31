---
name: screen-check
description: Prove a frontend change on the running screen - drive the real browser, click with a real pointer from a fresh entry, and report numbers that moved instead of an opinion. Use when the user asks to verify, fix, or refine anything visible in the web UI: layout, alignment, spacing, colour states, dialogs, grids, or whether a button actually works.
---

# Screen Check

A frontend claim is only as good as the number behind it. This skill is the order
that works and the traps that were measured — every rule below exists because a
plausible-looking verification passed while the screen was broken.

## Workflow

### 1. Use the stack that is already running

```bash
make ps                      # postgres / redis / phoenix
```

The dev servers are `hub` processes, not `bash` jobs. Check before starting one:
a second Vite silently takes the next port (`25173` → `5174`) and you end up
measuring a server the user is not looking at. Reuse the running one; it applies
your edit through HMR, and `curl -s http://localhost:25173/src/<path>.tsx` proves
which version it serves.

```
hub op:"start" name:"be" application:"make" args:["dev"] cwd:"backend"
  ready:{ log:"Application startup complete", port:28000 }
```

### 2. Get a session, then give it back

Seed an account over the API, log in through the form, and **delete the account
when done** — a list screen is the thing under test, and leftover test rows
change what the next measurement sees.

```bash
curl -s -X POST http://localhost:28000/api/v1/user/ -H 'Content-Type: application/json' \
  -d '{"username":"probe","email":"probe@example.com","password":"secret-pass"}'
```

Fill inputs through the native value setter, or React never sees the change:

```js
const el = c.querySelector('input')
Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(el, v)
el.dispatchEvent(new Event('input', { bubbles: true }))
```

### 3. Click the way a user clicks

**`element.click()` from `tab.evaluate` is not a click.** It skips hit testing,
overlays, and the browser's own `mousedown`/`mouseup`/`click` sequence. A dead
first click survived five verifications that all used it, and the bug was only
visible through the pointer:

```js
const h = await page.$('.MuiDataGrid-row [aria-label="상세"]')
const b = await h.boundingBox()
await page.mouse.click(b.x + b.width / 2, b.y + b.height / 2)
```

**Enter the screen fresh for every trial.** Navigate away and back, then click
once. Repeating a click on a page you already interacted with hides the entire
class of first-interaction bugs — focus, mount, refetch, node replacement.

### 4. Measure numbers, not impressions

A screenshot shows that something is wrong; a number says what and by how much,
and survives being wrong later. Read rects and computed styles:

| Claim | What to measure |
|---|---|
| "centred" | element centre minus container centre, and the two gaps |
| "aligned with the column beside it" | **ink**, not boxes — text via `range.selectNodeContents(cell)`, a glyph via its `<svg>` rect |
| "opens the dialog" | `[role=dialog]` count before and after |
| "the row is in edit mode" | `.MuiDataGrid-row--editing` count, plus the computed `backgroundColor` |
| "it refetched" | `performance.getEntriesByType('resource')` filtered by the endpoint |
| "nothing is clipped" | whether a child rect falls outside the cell's **border box** — `scrollWidth > clientWidth` is true for any content that overruns padding on purpose, and reports clipping that is not there |

Four traps that cost real time here:

- **A button box is not its glyph.** A 30px hit box holding a 20px glyph reads as
  5px of extra gutter; box arithmetic said 20/20 while the screen showed 20/25.
- **`window.fetch` patches catch nothing** when the app uses axios (XHR). Use
  resource entries, or a state change the request causes.
- **Framework layout is measured, not assumed.** Moving a hand-rolled cell to
  MUI's `type: 'actions'` kept a 4px gap constant while `.MuiDataGrid-actionsCell`
  uses 8px; the column came out 8px narrow and the gutter read 16px against the
  text's 20px. Read `getComputedStyle(...).gap` and the button rects instead.
- **Driving a screen writes to the database.** A stray click on a boolean cell
  flipped a seeded provider to disabled, and a later run measured that as the
  state. Read the row back and restore it — `PUT` bodies here forbid `code` and
  `version`, so send only the fields that changed.

### 4b. Use the probe, not fresh code each run

`.omp/hooks/lib/frontend-screen-probe.ts` holds the measurements these claims need,
so two runs report the same numbers instead of two hand-written variants:

| Function | Answers |
|---|---|
| `overflowReport()` | which cells clip, and whether each clipped one has a tooltip trigger |
| `columnBleedReport()` | does a cell draw over its neighbour (fixed shares past 100%) |
| `tooltipReport(pointer)` | the tooltip a hover produced, its gap above the cursor and its centring |
| `stripReport()` | is the action strip pinned, and where it sits after the body scrolled |
| `alertReport()` | the alerts in the dialog and the gap from the strip to the first one |

They are dependency-free DOM functions: paste the body into `tab.evaluate`, or read
the file and pass the function. `make verify` cannot run them — this repo has no
browser automation dependency, and adding one would put a Chromium download inside
every gate run. That is the reason geometry and interaction are measured here and
not asserted there.

### 5. When an event disappears, record a timeline

Do not guess through hypotheses. Log capture-phase `pointerdown`/`mousedown`/
`mouseup`/`click`, DOM `childList` mutations in the render zone, and network
entries with timestamps, then read the order:

```
 5ms mousedown  → button
10ms mouseup    → button
13ms removed path / added path      ← the pressed node was replaced
     click      ← never fired
```

That log named the cause in one run after three wrong hypotheses (tooltip, cell
focus, refetch timing) had each been rejected by an experiment.

### 6. Falsify the check, not just the code

A verification that passes proves nothing until it fails on a broken tree. Plant
the violation, watch it fire, restore:

- A style assertion that matched the **comment explaining the style** passed with
  the style deleted. Strip comments before testing code.
- A grid measurement on an empty grid returns "no rows", not a failure — guard
  for `null` or seed a row, or the run reports success against nothing.

### 7. Report what moved

Give the before/after table and name the mechanism. "Looks right" is not a
result; `52 → 67`, `0 → 1`, `25 → 20` are.

## Verification

- Every claim about the changed surface has a number from a browser run, taken
  from a fresh entry with a real pointer.
- Seeded rows and accounts are deleted; `git status` shows no stray fixtures.
- `make verify` is green, and any new invariant is enforced by a check that was
  proven to fire.

## Never Do These

- Verify a click with `element.click()`, or re-click a page you already touched.
- Start a second dev server instead of using the running one.
- Report a screenshot as proof of geometry, or an opinion as proof of behaviour.
- Leave the account or rows you seeded in the database.
- Keep a check that passes when the thing it guards is deleted.
