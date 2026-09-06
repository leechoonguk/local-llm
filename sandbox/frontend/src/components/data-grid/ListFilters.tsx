/**
 * One box per filterable column, and the control that clears them.
 *
 * A single keyword box over several columns cannot say which column it matched,
 * and a reader who wants "the account whose *email* contains probe" has to hope.
 * So each filterable column gets its own labelled box, named exactly as the
 * query parameter the router reads — the label says which column, the parameter
 * proves it.
 *
 * **Two kinds of box, and the column decides which.**
 *
 * | Kind | When | Renders | The router matches |
 * |---|---|---|---|
 * | text | free text: a code, a name, an alias list | a search field | contains (`ilike %v%`) |
 * | select | a closed vocabulary: a class, a status | a dropdown of the column's own values | equals |
 *
 * A field is a select the moment it carries `options`. The options are **the
 * ledger's distinct values, fetched** — never typed into the screen — because
 * the portal owns those vocabularies and the sync brings a new one the night it
 * appears; a list written here would offer yesterday's choices. So a screen with
 * select filters also reads a `facets` endpoint, and passes what it answers.
 *
 * The first option is "all", with the empty string as its value: the same empty
 * that `useListFilters` already treats as "no filter", so a select and a text
 * box clear the same way and the reset button needs no second rule.
 *
 * The reset is disabled until something is filtered, so the row never offers to
 * undo nothing. It is the error colour because it discards what the reader
 * typed, which is the only destructive thing on this row.
 */

import { IconButton, InputAdornment, MenuItem, TextField, Tooltip } from '@mui/material'
import Iconify from '@/components/iconify/Iconify'

const FIELD_WIDTH = 220

/** A select is narrower than a search box: its values are short and finite. */
const SELECT_WIDTH = 180

export interface ListFilterField {
  /** The query parameter, and the key into `values`. */
  name: string
  label: string
  /**
   * Present on a closed-vocabulary column: the values the box may take, as the
   * `facets` endpoint answered them. Absent on free text.
   */
  options?: readonly string[]
}

interface ListFiltersProps {
  fields: readonly ListFilterField[]
  values: Record<string, string>
  onChange: (name: string, value: string) => void
  isFiltered: boolean
  onReset: () => void
  resetLabel: string
  /** The "all" entry of every select — required as soon as any field has `options`. */
  allLabel?: string
}

export default function ListFilters({
  fields,
  values,
  onChange,
  isFiltered,
  onReset,
  resetLabel,
  allLabel,
}: ListFiltersProps) {
  return (
    <>
      {fields.map((field) =>
        field.options === undefined ? (
          <TextField
            key={field.name}
            size="small"
            label={field.label}
            value={values[field.name] ?? ''}
            onChange={(event) => onChange(field.name, event.target.value)}
            sx={{ width: { sm: FIELD_WIDTH } }}
            slotProps={{
              input: {
                startAdornment: (
                  <InputAdornment position="start">
                    <Iconify name="search" />
                  </InputAdornment>
                ),
              },
            }}
          />
        ) : (
          <TextField
            key={field.name}
            select
            size="small"
            label={field.label}
            value={values[field.name] ?? ''}
            onChange={(event) => onChange(field.name, event.target.value)}
            sx={{ width: { sm: SELECT_WIDTH } }}
            // `displayEmpty` shows the "all" entry while nothing is chosen, and a
            // label that does not shrink then prints over it - measured: 대분류
            // and 전체 rendered on the same baseline as one garbled word.
            slotProps={{ select: { displayEmpty: true }, inputLabel: { shrink: true } }}
          >
            <MenuItem value="">{allLabel ?? ''}</MenuItem>
            {field.options.map((option) => (
              <MenuItem key={option} value={option}>
                {option}
              </MenuItem>
            ))}
          </TextField>
        ),
      )}

      <Tooltip title={resetLabel}>
        <span>
          <IconButton color="error" disabled={!isFiltered} onClick={onReset}>
            <Iconify name="delete" />
          </IconButton>
        </span>
      </Tooltip>
    </>
  )
}
