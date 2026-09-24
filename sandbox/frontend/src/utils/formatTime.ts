/**
 * Timestamp formatting.
 *
 * The backend sends UTC ISO-8601 (`DateTime(timezone=True)` columns), and a
 * grid cell that prints the raw string shows a `T` and a `Z` to the user. One
 * formatter keeps every timestamp in the app identical, and an unparseable
 * value renders as a dash instead of `Invalid Date`.
 */

const EMPTY_VALUE = '-'

const FORMATTER = new Intl.DateTimeFormat('ko-KR', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

export function formatDateTime(value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return EMPTY_VALUE
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return EMPTY_VALUE
  return FORMATTER.format(parsed)
}

/**
 * A registry's own date (`20260915`) as a reader reads it (`2026-09-15`).
 *
 * The portals publish eight digits and this repository stores them verbatim -
 * the ledger is what the registry said. A screen is not a ledger: measured
 * 2026-09-16, the product dialog and the event table both printed the raw
 * digits, and a reader had to count characters to find the month.
 * Anything that is not eight digits is handed back as it came.
 */
export function formatPortalDate(value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const digits = /^(\d{4})(\d{2})(\d{2})$/.exec(value)
  return digits === null ? value : `${digits[1]}-${digits[2]}-${digits[3]}`
}
