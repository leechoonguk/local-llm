/**
 * Application-wide configuration.
 *
 * Every value the app reads at runtime lives here so a reader finds the wiring
 * in one file instead of grepping for a literal. The API base is a relative
 * path on purpose: Vite proxies it in dev and nginx proxies it in the image, so
 * the bundle never carries a host.
 */

export const API_BASE_URL = '/api/v1'

export const API_TIMEOUT_MS = 30_000

/**
 * The ceiling for one external execute from the integration screen.
 *
 * A CRUD call is answered by this backend; an execute is answered by a portal,
 * and then by this backend reading what it answered. Measured on the file door
 * of 수거검사: 62.8 MB downloaded in 4 s and 2,046,504 rows counted in 30 more,
 * 34.7 s in all - which the 30 s ceiling above cut off as "요청을 처리하지
 * 못했습니다" while the backend logged a success. The backend's own per-read
 * timeout on such an operation is 60 s, so a minute and a half covers a slow
 * portal without letting a dead one hold the screen.
 */
export const EXECUTE_TIMEOUT_MS = 90_000

export const APP_NAME = 'Fast API Standard'

export const DEFAULT_PAGE_SIZE = 10

export const PAGE_SIZE_OPTIONS = [10, 20, 50]

/** The backend caps `LimitQuery` at 100 — asking for more is a 422. */
export const MAX_PAGE_SIZE = 100

/**
 * Layout metrics, ported from the reference application's `config-global.ts`.
 * The header is fixed, so the main column's top padding is derived from its
 * height — a literal in one and not the other is how content ends up under the
 * bar on one screen only.
 */
export const HEADER = {
  H_MOBILE: 64,
  H_DESKTOP: 92,
  /** The scrolled height: the reference gives 32px back once the page moves. */
  H_DESKTOP_OFFSET: 92 - 32,
}

export const NAV = {
  W_DASHBOARD: 280,
  /**
   * The folded column: the icon with its label under it, nothing else.
   *
   * The reference's own width (measured: 87px, rounded to a spacing step here).
   * It is a second *layout*, not a hidden nav — the label stays, smaller, under
   * the glyph, so a folded sidebar still says which screen each row is.
   */
  W_MINI: 88,
  H_ITEM: 48,
  /** A mini row stacks two lines, so it is taller than the wide one. */
  H_ITEM_MINI: 58,
  H_ITEM_SUB: 36,
}

export const ICON = {
  NAV_ITEM: 24,
}

/** Gap between the fixed header and the first row of content. */
export const MAIN_SPACING = 8

/**
 * The tallest a select's dropdown may grow before it scrolls: eight and a half
 * rows, so the cut itself says there is more. MUI lets a `Select` menu take the
 * viewport - the 상태 filter's 86 values stood 804px tall from the top of the
 * screen, detached from the box that opened it - and gives an `Autocomplete`
 * listbox 40vh, which is a different height on every screen (measured
 * 2026-09-09: 338px at 844, 360 at 900). One number for both.
 */
export const SELECT_MENU_MAX_HEIGHT = 320

/**
 * The floor of a grid column that prints `formatDateTime`.
 *
 * One string on every screen, so one number: `2026. 8. 30. 오후 10:57` needs
 * 182px of cell at the body size, and a `width: 180` on the user list clipped
 * it to `10:...` while the report list beside it, at 185, did not.
 */
export const TIMESTAMP_COLUMN_FLOOR = 185

/**
 * Metrics of a record surface — the dialog, its section cards, its tables.
 *
 * They were literals inside five components, and each one that disagreed showed
 * up as a row of a different height beside its sibling: the operations table read
 * at 37px while the credentials table read at 43, one section header stood 70px
 * and another 62. Measured, then named here, so a new domain gets the rhythm by
 * importing it rather than by copying a number out of the exemplar.
 */
export const RECORD_SURFACE = {
  /**
   * The dialog body's floor. Measured at 420 it padded the landing tab with 261px
   * of empty neutral; the body follows its content and MUI's own
   * `calc(100% - 64px)` paper cap keeps a long form inside the viewport.
   */
  BODY_MIN_HEIGHT: 160,
  /**
   * One height for every section header. Measured without it: a header carrying an
   * action button was 70px and a text-only header 62px, so the title row moved as
   * the reader switched tabs. The taller is the floor — the button needs the room.
   */
  SECTION_HEADER_HEIGHT: 70,
  /** A table row at rest. A wrapped cell costs 20px of this, so cells clip. */
  TABLE_ROW_HEIGHT: 37,
  /** A row being edited: inputs are taller than the text they replace. */
  TABLE_EDIT_ROW_HEIGHT: 56,
  /** The action column's share of a nested table. */
  TABLE_ACTIONS_WIDTH: '10%',
  /** A select's own width, kept when the same field is read as text. */
  CHOICE_FIELD_WIDTH: 140,
  /**
   * The dialog's breakpoint, and the pixels its tables divide.
   *
   * `md` (900px) left a seven-column table 820px to share, and five of its
   * headers did not fit their share at the English reading - 'Annual capacity
   * (kg)' needs 180px and had 106 (measured 2026-09-16). `lg` is 1200, so a
   * table divides 1,120 after the dialog's 24px sides and the card's 16px, and
   * every header and badge stands whole. The number is named because
   * `check-frontend-screens` turns each column's percentage back into pixels
   * with it.
   */
  /**
   * The gap between two sibling cards of a record surface (16px), and the wider
   * one between two *groups* of cards (24px).
   *
   * Measured 2026-09-16 across the report dialog's seven tabs: the standards tab
   * stood its cards 16px apart and its type groups 24px apart, the nutrition and
   * label tabs stood theirs at 16px, and the record tab rendered its cards
   * straight into the dialog body with no stack at all - 0px, cards touching.
   * The standards tab is the reference because it is the one surface that draws
   * both rhythms; the two numbers are named here so a tab cannot invent a third,
   * and `check-frontend-screens` refuses a card stacked at anything else.
   */
  SECTION_GAP: 2,
  SECTION_GROUP_GAP: 3,
  DIALOG_MAX_WIDTH: 'lg' as const,
  TABLE_WIDTH: 1120,
}
