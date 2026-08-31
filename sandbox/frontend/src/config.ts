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
  H_ITEM: 48,
  H_ITEM_SUB: 36,
}

export const ICON = {
  NAV_ITEM: 24,
}

/** Gap between the fixed header and the first row of content. */
export const MAIN_SPACING = 8

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
}
