---
description: Frontend component boundaries — when a shape is extracted, when it is copied, and what may never be written twice
globs:
      - frontend/src/components/**/*.tsx
      - frontend/src/sections/**/*.tsx
      - frontend/src/layouts/**/*.tsx
      - .omp/hooks/lib/frontend-component-split.ts
alwaysApply: false
---

# Frontend Component Boundaries

## Purpose

Two pieces of UI look alike. This rule answers whether that means "extract a
component", "copy the shape", or "you wrote one thing twice" — and which of the
three a check can tell apart.

## The Distinction That Decides It

**Shape may be copied between screens. A shape may not be written twice inside
one of them.**

- Between two screens of the same *type*, similarity is the standard. `BatchList`
  and `UserList` share **93 of 117** normalised lines and that is deliberate: a
  generic `<CrudList domain={…}>` hides the columns, the dialogs and the empty
  sentence behind configuration, and the first screen that needs one exception
  forks it. The shape is copied; the decisions stay local. `BatchList`'s own
  comment says so, and `check-frontend-components` never compares two files'
  bodies for this reason.
- Inside one file, a repeated shape is a defect: a change reaches one copy, and
  the screen shows both. Measured: the run panel grew a second
  status-plus-payload section for the failure case, above the inputs that produced
  it, and a failed re-run left the previous success on screen underneath the new
  error.

## Principles

1. **One section per shape.** Two sibling sections whose tag sequence is the same
   are one section with the difference inside it —
   `Stack>Stack>Typography>Label>Payload` inside
   `Stack>Divider>Stack>Typography>Label>Payload>Payload` was the failure result
   beside the success result.
2. **One concept per component.** Two exports that agree are one export plus a
   prop. The shape that is *right* is in the tree: `ScalarField` renders a read
   and an edit in one component behind `readOnly`, so the two can never disagree
   about what the value is.
3. **One record, one screen; a mode is state.** No `*CreatePanel` beside
   `*EditPanel`, no read-only twin of a panel that also edits. This repo already
   replaced that pair: they differed only in which mode the door landed in, and
   editing is panel state so the record stays scrolled where it was.
4. **One outcome, one place that shows it.** A panel holds the whole outcome in
   one value; it never renders a mutation hook's `.data` beside its own failure
   state (`rule://frontend-screens`, enforced by `check-frontend-screens`).
5. **Extract when a second caller already exists *and* the frame owns an
   invariant.** Every extraction in this repo has both:

   | Component | Callers | The invariant it owns |
   |---|---|---|
   | `PanelStrip` | 4 panels | the strip is pinned, one line, leaving on the line above |
   | `PagedTableSection` | 2 tabs | row height, footer, the empty sentence (83 of 118 lines were identical before it) |
   | `RecordDeletePanel` | 2 delete panels | one cancel, one pinned strip, the cost sentence |
   | `ClippedText` | every grid cell and detail table | a clipped value is reachable on hover |
   | `RecordFields` | panels that read and edit | `readOnly` + `aria-readonly` written once |

6. **Never extract for similarity alone.** A component with one caller that owns
   no invariant is a file to open on the way to the code that matters.
7. **A shared frame owns numbers, not decisions.** Layout metrics come from
   `RECORD_SURFACE` in `config.ts`, so two files cannot drift by 6px; the columns,
   the verbs and the sentences stay in the screen that shows them.

## How It Is Checked

`check-frontend-components` reads `lib/frontend-component-split.ts`. The metric is
the **tag sequence**, not the lines: comparing normalised lines scored the real
defect at 0.27, because the two sections printed different values and almost no
line matched.

| Rule | What fires | Threshold, measured |
|---|---|---|
| one section per shape | one sibling block's tag sequence is a subsequence of another's | ≥ 4 tags, and ≥ 2 **named** components in the shared shape |
| one concept per component | two exported components' bodies agree | ≥ 85% of normalised lines |
| one record, one screen | two file names differing only by `Create`/`Edit`/`Update`/`New`/`Read`/`View`/`Success`/`Error`/`Failure` | any pair |

The named-component threshold is why the check is quiet on the tree: containment
alone reported three pairs in `IntegrationOperationFieldsEditor`, all of the form
`Stack>IconButton>Iconify>IconButton>Iconify` inside a longer row — a shape built
only from primitives is a layout row, not a section. With the split, the tree
reports nothing and each planted defect reports itself.

## Never Do These

- Render the same section shape twice with a condition around each.
- Add a `*Create*`/`*Edit*`/`*View*` twin of a screen that already holds the record.
- Extract a component with one caller and no invariant.
- Factor two screens of the same type into one configurable screen.
- Keep a success in a mutation's `data` and a failure in a second state.
