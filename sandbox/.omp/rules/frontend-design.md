---
description: Frontend design system — theme tokens, layout metrics, and the ported component vocabulary
globs:
      - frontend/src/theme/**/*.ts
      - frontend/src/theme/**/*.tsx
      - frontend/src/components/**/*.tsx
      - frontend/src/layouts/**/*.tsx
      - frontend/src/sections/**/*.tsx
      - frontend/src/styles.css
alwaysApply: false
---

# Frontend Design

The design is ported, not invented: the palette, the type scale, the shadows and
the component vocabulary come from the reference application (`Food start`), and
the values are exact. A screen that picks its own green, its own radius or its
own shadow does not look "slightly different" — it looks broken next to the
screen beside it.

Machine-checked by `check-frontend-design.ts` (`make check-frontend-design`).

## Where the Design Lives

| File | Owns |
|---|---|
| `theme/palette.ts` | every colour, including `background.neutral` and each colour's `lighter`/`darker` |
| `theme/typography.ts` | the type scale — `pxToRem`, weights, responsive heading sizes |
| `theme/shadows.ts` | the 25-step elevation array **and** the named `customShadows` (`card`, `dialog`, `dropdown`) |
| `theme/overrides.ts` | component defaults — card radius and shadow, dialog shape, tab metrics, table head, input border |
| `config.ts` | layout metrics — `HEADER`, `NAV`, `ICON`, `MAIN_SPACING` |
| `styles.css` | a document reset and nothing else |

`styles.css` is deliberately three rules long. It previously carried the stub
app's page layout (`max-width: 40rem` on `:root`), which clamped the whole
document and squeezed the shell into a 230px strip no matter what the layout
asked for — a stylesheet that lays out pages competes with the theme and wins
silently.

## Component Vocabulary

These exist so a screen never re-solves a solved problem:

| Component | Use |
|---|---|
| `components/label/Label` | every status/enum badge — 24px, radius 6, bold 12px, `soft` tint |
| `components/page-header/PageHeader` | heading, description, dot-separated breadcrumbs, right-aligned action |
| `components/data-grid/ListToolbar` | the tab strip with the row count plus the action row |
| `components/data-grid/RowActions` | `rowActionsColumn` — the last column of a grid: every per-row intent as a visible icon button, never a `⋮` menu and never the row click |
| `components/data-grid/ServerDataGrid` | the only place MUI's `DataGrid` is rendered |
| `components/detail/DetailSection` | a titled white card inside a neutral detail body |
| `components/detail/DetailField` | one caption/value pair |
| `components/card/StatCard` | one dashboard number, with its own loading and failure states |
| `components/iconify/Iconify` | every inline icon, by registry name |
| `components/svg-color/SvgColor` | every navigation glyph, masked over `currentColor` |
| `components/menu-popover/MenuPopover` | every header menu: a 12px arrow aimed at its button, inset rounded `body2` rows |

## Icons: Two Systems, Split by Role

The reference application uses two, and so does this one. Mixing them is what
makes a screen look "slightly off": an outline icon beside a filled one beside a
third family's bold one is three drawings of the same idea.

| System | Where | How |
|---|---|---|
| `ACTION_ICONS` | inline UI — buttons, menus, tabs, alerts | Iconify **eva** set, **filled** variants only (`eva:edit-fill`), through `<Iconify name="edit" />` |
| `NAV_ICONS` | the sidebar | local SVGs in `public/assets/icons/navbar/`, through `<SvgColor src={NAV_ICONS.user} />` |

`SvgColor` masks the file over `currentColor`, which is why a nav icon turns
primary the moment its item is active — an `<img>` cannot inherit colour.

`components/iconify/icons.ts` is the only module that spells an icon id or an
asset path. A screen names what it means (`add`, `delete`, `more`), so changing
what "delete" looks like is one edit instead of a grep, and a raw
`icon="mdi:…"` is rejected.

## Rules

- **No colour literal in a component.** No `#rrggbb`, `rgb(`, or `hsl(` outside
  `theme/palette.ts`. Colours are read as tokens (`primary.main`,
  `text.secondary`, `background.neutral`) or tinted with `alpha(theme.palette…)`.
- **No `boxShadow` literal.** Use `theme.customShadows.*`, or let the component
  override in the theme do it.
- **No `fontSize` / `fontWeight` literal.** Use a `variant`; if the variant does
  not exist, the type scale is what changes.
- **No layout metric literal.** The header height and nav width come from
  `config.ts` — a literal in one place and a constant in another is how content
  ends up under the fixed header on one screen only.
- **`Chip` is not a status badge.** `Label` is, and it is the same badge in a
  grid cell, a dialog header and a tab count.
- **A detail body is `background.neutral` with white section cards.** That
  contrast is what separates the record from the page.
- **A container that accepts children spaces them; a caller never has to.**
  `DetailSection`'s body is `<Stack spacing={2}>`. Measured without it: `rowGap:
  normal`, so a table and the block below it touched at **0px** — a
  `TablePagination` survived on its own padding, an `Alert` read as glued to the
  last row. The gap belongs to the container for the same reason the gap between
  two cards belongs to their parent: a caller that has to remember it forgets once.
- **A row being edited is marked by the action colour and an edge bar, never by
  `warning`.** `EDITING_ROW_SX` — `alpha(primary.main, 0.08)` plus
  `inset 3px 0 primary.main` — exported from `ServerDataGrid` so the grid and a
  plain editing `TableRow` cannot drift. Amber was the first attempt and the wrong
  word: `warning.lighter` is this palette's caution (a delete panel's alert, a
  field the server would reject), and a row someone chose to edit is not a
  caution — spending the caution colour on an ordinary action leaves nothing
  louder for a real one. The bar carries the state without hue, so the row
  survives greyscale and colour-blind vision (WCAG 1.4.1). The wash covers
  `:hover` too, or moving the mouse erases the one signal that unsaved changes
  exist, and the cell background is cleared because MUI's own editing style — a
  white cell with a shadow — is invisible on a white table.
- **The focused cell is ringed for keyboards, not for the pointer that aimed.**
  MUI X rings on `:focus-within`, so clicking a row's pencil drew a second green
  rectangle around the action buttons while the row already said it was editing.
  `:focus` and `:focus-within` are cleared; `:focus-visible` keeps the ring on the
  cell (arrow-key navigation has no other cue) and a 2px ring on a focused button.
  Never drop the indicator entirely — WCAG 2.4.7 requires focus to be visible.
- **An edit control is the same control the forms use.** `type: 'boolean'` edits
  through a bare checkbox, the one control that appears nowhere else: the read
  cell is a `Label` chip and both form dialogs use a `Switch`. A boolean column
  overrides `renderEditCell` with that switch, which reads as the state it is in
  rather than as a box being ticked.
- **A glyph never takes pointer events.** `Iconify` is `pointerEvents: 'none'`, so
  the button around it is the event target. `@iconify/react` re-creates its `<path>`
  nodes on re-render; inside a grid cell that lands between `mouseup` and the
  browser's `click` dispatch, and the click is dropped with no error anywhere.
- **A child that pushes itself to the edge needs its parent on `gap`.** `Stack
  spacing={n}` writes `margin-left: 8n` onto every child after the first, from a
  selector on the parent — which outranks the child's own `sx`, so `ml: 'auto'`
  computes to that margin and the child does not move. `useFlexGap` switches the
  parent to `gap` and the auto margin works. Measured twice in one screen: the
  panel strip's verbs sat against the method badge with 457px of empty row to
  their right while the component's own comment claimed they were at the edge, and
  the field editor's segment-order controls sat against the switches.

## Review Judgement (not machine-checked)

- Whether a repeated `sx` block should have become a theme default.
- Whether the chosen token is the right one — `text.secondary` on a heading
  passes the check and still reads as a mistake.
- Which layout metrics are checked: the three the shell depends on
  (`NAV.W_DASHBOARD`, `HEADER.H_DESKTOP`, `HEADER.H_MOBILE`), matched at
  size and offset props. A new shared metric has to be added to the check with
  the constant, or it is only documented here.
- Whether an icon name means what the screen needs. The registry keeps one
  family; it cannot say that `link` was the wrong glyph for that button.

## Never Do These

- Write a hex colour, `rgb()` or `hsl()` anywhere outside `theme/palette.ts`
- Write a `boxShadow` string in a component
- Pass a raw icon id (`icon="mdi:account"`) — name it in `components/iconify/icons.ts`
- Mix icon families or weights — inline icons are eva, filled
- Render a navigation glyph with `Iconify` — nav icons are `SvgColor` over a local SVG
- Set `fontSize` or `fontWeight` instead of choosing a typography variant
- Hardcode the nav width or header height
- Use `Chip` where `Label` is the design
- Put page layout in `styles.css`
- Set `borderRadius` on a `Card` — the theme already does, at twice the base
