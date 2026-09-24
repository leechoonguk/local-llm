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
 * | select | a closed vocabulary: a class, a status | a dropdown the reader can type into | equals |
 *
 * A field is a select the moment it carries `options`. The options are **the
 * ledger's distinct values, fetched** — never typed into the screen — because
 * the portal owns those vocabularies and the sync brings a new one the night it
 * appears; a list written here would offer yesterday's choices. So a screen with
 * select filters also reads a `facets` endpoint, and passes what it answers.
 *
 * **A select is typed into, not only scrolled.** The vocabularies are the
 * columns' own values and some are long - 814 식품유형 on the item report
 * list, 85 상태 on the raw material one (measured 2026-09-09) - and a reader
 * who knows the value they want should not hunt for it in a list that height.
 * So the box is an `Autocomplete`: typing narrows the options by contains,
 * and what it sends is still one of them, so the router's equals holds. A
 * plain dropdown was the first shape and it is right only while a vocabulary
 * is short, which is a property of the data, not of the screen.
 *
 * Cleared is "all", the empty string `useListFilters` already treats as no
 * filter, so a select and a text box clear the same way and the reset button
 * needs no second rule; `allLabel` is what the empty box says.
 *
 * The boxes are never disabled, not even while a page is in flight: the
 * fetch fires 300ms after the last keystroke, and a box that locks then cuts
 * the word the reader is still typing (measured: `밀가` sent, `루` dropped).
 * The race a locked box would prevent is closed by the query key instead -
 * a newer key supersedes the older request's answer.
 *
 * The reset is disabled until something is filtered, so the row never offers to
 * undo nothing. It is the error colour because it discards what the reader
 * typed, which is the only destructive thing on this row.
 */

import { Autocomplete, InputAdornment, TextField } from '@mui/material'
import Iconify from '@/components/iconify/Iconify'

export interface ListFilterField {
  /** The query parameter, and the key into `values`. */
  name: string
  label: string
  /**
   * Present on a closed-vocabulary column: the values the box may take, as the
   * `facets` endpoint answered them. Absent on free text.
   */
  options?: readonly string[]
  /**
   * How an option reads. A facets value is the row's own text and reads as
   * itself; a *code* the schema closes (`food` / `livestock`) is not a word a
   * reader knows, so a field whose options are codes owes the translation here.
   * `check-frontend-screens` demands it wherever `options` is not a facets read.
   */
  optionLabel?: (value: string) => string
}

interface ListFiltersProps {
  fields: readonly ListFilterField[]
  values: Record<string, string>
  onChange: (name: string, value: string) => void
  /** What an empty select says — required as soon as any field has `options`. */
  allLabel?: string
  /** MUI's own Autocomplete strings, in the reader's language. */
  noOptionsLabel?: string
  clearLabel?: string
  openLabel?: string
  closeLabel?: string
}

export default function ListFilters({
  fields,
  values,
  onChange,
  allLabel,
  noOptionsLabel,
  clearLabel,
  openLabel,
  closeLabel,
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
            fullWidth
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
          <Autocomplete
            key={field.name}
            size="small"
            fullWidth
            options={field.options}
            // The value is the column's, not the label's: an empty box is "all".
            value={values[field.name] === '' || values[field.name] === undefined ? null : values[field.name]}
            onChange={(_event, option) => onChange(field.name, option ?? '')}
            getOptionLabel={(option) =>
              field.optionLabel === undefined ? option : field.optionLabel(option)
            }
            // MUI's own strings, or the listbox says "No options" inside a Korean screen.
            noOptionsText={noOptionsLabel}
            clearText={clearLabel}
            openText={openLabel}
            closeText={closeLabel}
            renderInput={(params) => (
              <TextField {...params} label={field.label} placeholder={allLabel} />
            )}
          />
        ),
      )}

    </>
  )
}
