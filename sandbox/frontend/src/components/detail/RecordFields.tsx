/**
 * The three field shapes a record panel needs, each reading as text and editing
 * as an input.
 *
 * Reading a record through disabled inputs is what the accessibility guidance
 * calls out: the reduced opacity and the input chrome make values harder to read
 * than plain text, and a disabled control is exempt from contrast rules and
 * skipped by assistive technology. So a read is `DetailField` — a caption above a
 * value — and an edit is the control.
 *
 * They live here because two panels needed them and only one had them: the
 * operation panel declared this trio privately while the credential panel wrote
 * the same branch by hand, one `readOnly ? … : …` around its whole body. That is
 * how the `readOnly` input and its `aria-readonly` pair get written twice and
 * then disagree.
 */

import { Box, MenuItem, TextField } from '@mui/material'
import DetailField from '@/components/detail/DetailField'
import { RECORD_SURFACE } from '@/config'

/** The select's own width, kept when the same field is read as text. */
const CHOICE_FIELD_WIDTH = RECORD_SURFACE.CHOICE_FIELD_WIDTH

/**
 * One value out of a fixed set. Reading, it is the value — a disabled select
 * greys the one thing the reader came for, and a dropdown arrow on a record that
 * cannot change is an affordance that lies.
 */
export function ChoiceField({
  label,
  value,
  options,
  readOnly,
  onChange,
}: {
  label: string
  value: string
  options: readonly string[]
  readOnly: boolean
  onChange: (value: string) => void
}) {
  if (readOnly) {
    return (
      <Box sx={{ minWidth: CHOICE_FIELD_WIDTH }}>
        <DetailField label={label}>{value}</DetailField>
      </Box>
    )
  }
  return (
    <TextField
      select
      label={label}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      size="small"
      sx={{ minWidth: CHOICE_FIELD_WIDTH }}
    >
      {options.map((option) => (
        <MenuItem key={option} value={option}>
          {option}
        </MenuItem>
      ))}
    </TextField>
  )
}

/**
 * One scalar.
 *
 * `immutable` is a value that cannot change but must stay legible and tabbable —
 * `readOnly`, never `disabled`. A record's key is the case: it addresses the row
 * the request will resolve, so an edit form shows it and refuses to change it.
 */
export function ScalarField({
  label,
  value,
  readOnly,
  immutable = false,
  type,
  placeholder,
  maxLength,
  error = false,
  helperText,
  onChange,
}: {
  label: string
  value: string
  readOnly: boolean
  immutable?: boolean
  type?: 'password'
  placeholder?: string
  maxLength?: number
  error?: boolean
  helperText?: string
  onChange: (value: string) => void
}) {
  if (readOnly) {
    return (
      <Box sx={{ flexGrow: 1 }}>
        <DetailField label={label}>{value === '' ? undefined : value}</DetailField>
      </Box>
    )
  }
  return (
    <TextField
      label={label}
      value={value}
      type={type}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      error={error}
      helperText={helperText}
      size="small"
      fullWidth
      slotProps={{
        input: { readOnly: immutable },
        htmlInput: { 'aria-readonly': immutable, maxLength },
      }}
    />
  )
}

/** A number, read as its digits and edited through a field that rejects letters. */
export function NumberField({
  label,
  value,
  readOnly,
  min,
  max,
  onChange,
}: {
  label: string
  value: number
  readOnly: boolean
  /**
   * The bound the server declares for this field.
   *
   * Non-digits are stripped below, so a negative never reaches the API — but `0`
   * does, and it is exactly what an emptied input hands back. A field the server
   * refuses at `gt=0` therefore needs its own floor here, or the user learns the
   * rule from a 422 with no field named.
   */
  min?: number
  max?: number
  onChange: (value: number) => void
}) {
  if (readOnly) {
    return (
      <Box sx={{ flexGrow: 1 }}>
        <DetailField label={label}>{String(value)}</DetailField>
      </Box>
    )
  }
  const outOfRange = (min !== undefined && value < min) || (max !== undefined && value > max)
  return (
    <TextField
      label={label}
      value={value}
      onChange={(event) => onChange(Number(event.target.value.replace(/\D/g, '')) || 0)}
      size="small"
      fullWidth
      error={outOfRange}
      slotProps={{ htmlInput: { inputMode: 'numeric', min, max } }}
    />
  )
}
