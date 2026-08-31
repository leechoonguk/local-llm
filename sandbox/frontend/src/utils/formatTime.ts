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
