/// <reference lib="dom" />

/**
 * The measurements a screen claim needs, written once.
 *
 * `make verify` cannot run these: there is no browser automation dependency in
 * this repo, and adding one would put a headless Chromium download inside every
 * `make verify`. So geometry and interaction stay agent-measured — through
 * `skill://screen-check` — and this file is what keeps those measurements the
 * same numbers every run instead of ad-hoc code each time.
 *
 * The functions are dependency-free DOM code on purpose: they are meant to be
 * handed to the browser tool's `tab.evaluate`, where nothing but the page exists.
 * They are typed against the DOM lib rather than the app, so they never drift with
 * a component rename.
 *
 * Every one returns numbers, never a verdict. The caller decides what counts as a
 * failure, and a report of numbers survives being wrong later.
 */

/** A pointer position, as the browser tool reports it after a real mouse move. */
export interface PointerPosition {
  x: number
  y: number
}

export interface OverflowRow {
  field: string | null
  text: string
  clipped: boolean
  hasTrigger: boolean
}

/**
 * Which cells clip, and whether the clipped ones can be read on hover.
 *
 * `scrollWidth > clientWidth` is the only honest overflow test — a screenshot
 * cannot tell a clipped value from a short one. A clipped cell with no tooltip
 * trigger is the defect this catches: the value exists nowhere on screen.
 */
export function overflowReport(): OverflowRow[] {
  const cells = Array.from(document.querySelectorAll<HTMLElement>(".MuiDataGrid-cell, td"))
  return cells
    .map((cell) => {
      const inner = cell.firstElementChild
      const measured = inner instanceof HTMLElement ? inner : cell
      return {
        field: cell.getAttribute("data-field"),
        text: (cell.textContent ?? "").trim().slice(0, 40),
        clipped: measured.scrollWidth > measured.clientWidth + 1,
        // `ClippedText` renders its own span; a bare cell has no element child.
        hasTrigger: inner !== null && inner.tagName === "SPAN",
      }
    })
    .filter((row) => row.clipped)
}

/**
 * Does a cell draw over its neighbour?
 *
 * A fixed layout whose declared shares exceed 100% pushes its last columns past
 * the table edge and the long value draws across them. Comparing one cell's right
 * edge to the next cell's left edge is what shows it; `scrollWidth` does not,
 * because content that overruns padding on purpose reports the same.
 */
export function columnBleedReport(): Array<{ index: number; overlap: number }> {
  const bleeding: Array<{ index: number; overlap: number }> = []
  for (const row of Array.from(document.querySelectorAll<HTMLTableRowElement>("table tbody tr"))) {
    const cells = Array.from(row.querySelectorAll<HTMLTableCellElement>("td"))
    for (let index = 0; index < cells.length - 1; index += 1) {
      const here = cells[index].getBoundingClientRect()
      const next = cells[index + 1].getBoundingClientRect()
      if (here.right > next.left + 1) {
        bleeding.push({ index, overlap: Math.round(here.right - next.left) })
      }
    }
  }
  return bleeding
}

/** The tooltip a hover produced, and where it sits relative to the pointer. */
export function tooltipReport(pointer: PointerPosition): {
  text: string
  gapAboveCursor: number
  centredOnCursor: number
  width: number
} | null {
  const tip = document.querySelector<HTMLElement>("[role=tooltip]")
  if (tip === null) return null
  const rect = tip.getBoundingClientRect()
  return {
    text: (tip.textContent ?? "").trim(),
    gapAboveCursor: Math.round(pointer.y - rect.bottom),
    centredOnCursor: Math.round(rect.x + rect.width / 2 - pointer.x),
    width: Math.round(rect.width),
  }
}

/** The one sticky row inside the open dialog, if it has one. */
function stickyStrip(dialog: HTMLElement): HTMLElement | undefined {
  return Array.from(dialog.querySelectorAll<HTMLElement>("div")).find(
    (node) => getComputedStyle(node).position === "sticky",
  )
}

/**
 * Is the panel's action strip still reachable after the body scrolled?
 *
 * Measured defect: a 204-field record is 933px of body against a 686px viewport,
 * and an action at the bottom of that is an action nobody scrolled to. A sticky
 * strip reports the same `stripTop` before and after the scroll.
 */
export function stripReport(): {
  pinned: boolean
  stripTop: number | null
  buttons: string[]
  scrollTop: number | null
  scrollHeight: number | null
  clientHeight: number | null
} | null {
  const dialog = document.querySelector<HTMLElement>("[role=dialog]")
  if (dialog === null) return null
  const strip = stickyStrip(dialog)
  const body = dialog.querySelector<HTMLElement>(".MuiDialogContent-root")
  return {
    pinned: strip !== undefined,
    stripTop: strip === undefined ? null : Math.round(strip.getBoundingClientRect().top),
    buttons:
      strip === undefined
        ? []
        : Array.from(strip.querySelectorAll<HTMLElement>("button")).map((button) =>
            (button.textContent ?? "").trim(),
          ),
    scrollTop: body === null ? null : Math.round(body.scrollTop),
    scrollHeight: body === null ? null : Math.round(body.scrollHeight),
    clientHeight: body === null ? null : Math.round(body.clientHeight),
  }
}

/** Alerts in the dialog, and the distance from the pinned strip to the first one. */
export function alertReport(): {
  count: number
  texts: string[]
  gapFromStrip: number | null
} | null {
  const dialog = document.querySelector<HTMLElement>("[role=dialog]")
  if (dialog === null) return null
  const strip = stickyStrip(dialog)
  const alerts = Array.from(dialog.querySelectorAll<HTMLElement>(".MuiAlert-root"))
  return {
    count: alerts.length,
    texts: alerts.map((alert) => (alert.textContent ?? "").trim().slice(0, 60)),
    gapFromStrip:
      strip === undefined || alerts.length === 0
        ? null
        : Math.round(alerts[0].getBoundingClientRect().top - strip.getBoundingClientRect().bottom),
  }
}
