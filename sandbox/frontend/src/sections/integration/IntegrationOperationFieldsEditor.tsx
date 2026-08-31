/**
 * The wire mapping editor — two tables, one per direction.
 *
 * Design decisions, each answering something that was measured:
 *
 * 1. **Direction is a section, not a column.** A field row carries sixteen
 *    columns, and half of them only exist in one direction: REQUEST rows carry a
 *    `value_source`, `value` and `secret_name`, RESPONSE rows never do. One table
 *    with both would be mostly empty cells, and the detail panel already reads as
 *    two tables — the editor mirrors it so read and write look like one screen.
 * 2. **Rows are text; one row at a time is a form.** Rendering every row as
 *    inputs mounted 635 MUI controls for a 204-field operation: the panel took
 *    **14.9 seconds** to appear and a single keystroke in an unrelated field cost
 *    **332ms**, while the same 204 rows read-only mount in **150ms**. So a row is
 *    text until it is picked, exactly as the list grids edit in place. The
 *    server-side story is not the slow part — the same save is a 45–97ms `PUT`.
 * 3. **The row's shape follows its `value_source`.** CALLER supplies the value at
 *    run time, LITERAL needs one now, SECRET names one of the provider's
 *    credentials, CONTEXT is resolved by the server. Rendering every input for
 *    every source is how a LITERAL row with an empty value reaches the server and
 *    comes back 422 with nothing on screen to explain it.
 * 4. **`location` decides what `wire_path` means, so the editor checks it.** A
 *    PATH row's key has to appear as `{key}` in the operation's path template, or
 *    the request is built against a URL that still has a placeholder in it.
 * 5. **Five columns, then a disclosure.** All eight editable columns measured
 *    1076px inside an 852px dialog body, and the right-hand ones were cut off.
 *    Type, format, description, sensitivity and header matching are per-row
 *    attributes, so they live in the picked row's expansion — which is also the
 *    only place they have ever been editable.
 * 6. **Ordinal is row order**, assigned from the index on save. Order matters for
 *    path segments, so the arrows sit with the picked row.
 * 7. **No third surface.** The stack is already provider dialog → operation
 *    panel; a modal for one row would be a third layer over a record the user is
 *    still editing.
 */

import { Fragment, memo, useCallback, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Collapse,
  FormControlLabel,
  IconButton,
  MenuItem,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import { useTranslation } from 'react-i18next'
import { RowActionButtons } from '@/components/data-grid/RowActions'
import { EDITING_ROW_SX } from '@/components/data-grid/ServerDataGrid'
import { RECORD_SURFACE } from '@/config'
import ClippedText from '@/components/detail/ClippedText'
import Iconify from '@/components/iconify/Iconify'
import type {
  FieldDirection,
  FieldLocation,
  HeaderMatchMode,
  IntegrationFieldCreateRequest,
  RequestValueSource,
  ValueType,
} from '@/types/integration'

const REQUEST_LOCATIONS: FieldLocation[] = ['PATH', 'PATH_QUERY', 'QUERY', 'HEADER', 'BODY']

const RESPONSE_LOCATIONS: FieldLocation[] = ['BODY', 'ENVELOPE', 'HEADER']

const VALUE_SOURCES: RequestValueSource[] = ['CALLER', 'LITERAL', 'SECRET', 'CONTEXT']

const VALUE_TYPES: ValueType[] = [
  'STRING',
  'INTEGER',
  'NUMBER',
  'BOOLEAN',
  'DATE',
  'DATETIME',
  'JSON',
  'EPOCH_SECONDS',
  'HTTP_DATE',
  'DURATION_SECONDS',
]

const MATCH_MODES: HeaderMatchMode[] = ['IGNORE', 'PRESENT', 'EXACT', 'ONE_OF']

/**
 * Only `PATH` is substituted into the template, so only `PATH` needs the template
 * to name it. `PATH_QUERY` is **appended** — the backend joins those fields with
 * `&` and hangs them off the end (`path.rstrip('/') + '/' + '&'.join(filters)`),
 * so it carries a wire name, not a placeholder. Measured: the seeded
 * `search-product-classification` has `last_updated_from` at `PATH_QUERY`, and
 * lumping the two together reported `REQUEST #6: {last_updated_from}` and left
 * `저장` dead — a correct record the screen refused to save.
 */
const PLACEHOLDER_LOCATIONS: FieldLocation[] = ['PATH']

/**
 * Declared widths, because `table-layout: auto` sizes each column to its widest
 * cell and the two tables would then disagree with each other. The sum is what
 * fits the dialog body: 852px measured, 776px used.
 */
const COLUMN_WIDTH = {
  key: 150,
  location: 120,
  wirePath: 180,
  valueSource: 118,
  value: 140,
  actions: 68,
} as const

const READ_ROW_HEIGHT = RECORD_SURFACE.TABLE_ROW_HEIGHT
const EDIT_ROW_HEIGHT = RECORD_SURFACE.TABLE_EDIT_ROW_HEIGHT
const ADVANCED_FIELD_WIDTH = 200

export interface FieldRow extends IntegrationFieldCreateRequest {
  /** Stable across renders so an edited row does not remount on every keystroke. */
  rowId: string
}

let rowSeed = 0

export const emptyFieldRow = (direction: FieldDirection): FieldRow => {
  rowSeed += 1
  return {
    rowId: `${direction}-${rowSeed}`,
    direction,
    location: direction === 'REQUEST' ? 'QUERY' : 'BODY',
    key: '',
    wire_path: '',
    value_source: direction === 'REQUEST' ? 'CALLER' : null,
    value: null,
    secret_name: null,
    value_type: 'STRING',
    format: null,
    required: direction === 'REQUEST',
    description: null,
    sensitive: false,
    enabled: true,
    match_mode: null,
    expected_values: null,
  }
}

interface IntegrationOperationFieldsEditorProps {
  direction: FieldDirection
  rows: FieldRow[]
  secretNames: string[]
  pathTemplate: string
  /**
   * A functional update, not a new array from the caller. A callback built from
   * the current `rows` is a new function on every keystroke, which breaks the
   * memo on all two hundred resting rows — measured as 133ms a character until
   * the updater made the callbacks stable.
   */
  onChange: (update: (rows: FieldRow[]) => FieldRow[]) => void
  /**
   * The same tables, reading. The record's view and its form are one surface, so
   * the rows are rendered by this component in both — what a read mode drops is
   * the add button and the per-row actions, never the columns, or the two modes
   * would disagree about what a field is.
   */
  readOnly?: boolean
}

export default function IntegrationOperationFieldsEditor({
  direction,
  rows,
  secretNames,
  pathTemplate,
  onChange,
  readOnly = false,
}: IntegrationOperationFieldsEditorProps) {
  const { t } = useTranslation('integration')
  const { t: tCommon } = useTranslation('common')
  const [picked, setPicked] = useState<string | null>(null)
  const [detailed, setDetailed] = useState(false)

  /**
   * Collapsed when the section already has rows, open when it has none.
   *
   * A 204-row section pushes the operation's own eight inputs off the screen, and
   * the panel's job on open is the operation, not its two hundred field rows —
   * the count in the header is what a reader needs before deciding to look. An
   * empty section is the opposite case: hiding it would hide the only place a new
   * operation can declare anything, so it starts open with its sentence showing.
   */
  const [open, setOpen] = useState(
    () => rows.filter((row) => row.direction === direction).length === 0,
  )
  const isRequest = direction === 'REQUEST'
  const mine = rows.filter((row) => row.direction === direction)
  /**
   * The rows at rest are told their verdict, not the path to judge themselves by.
   * `pathTemplate` changes on every keystroke in the operation's path field, and
   * a row that receives it re-renders with it — measured as 140ms a character
   * across two hundred rows. A joined string is stable when nothing changed, so
   * only the rows whose verdict moved are re-rendered.
   */
  const issuesByRow = useMemo(
    () => new Map(rows.map((row) => [row.rowId, rowIssues(row, pathTemplate).join(', ')])),
    [rows, pathTemplate],
  )

  const patch = useCallback(
    (rowId: string, next: Partial<FieldRow>) => {
      onChange((current) =>
        current.map((row) => (row.rowId === rowId ? { ...row, ...next } : row)),
      )
    },
    [onChange],
  )

  const remove = useCallback(
    (rowId: string) => {
      setPicked((current) => (current === rowId ? null : current))
      onChange((current) => current.filter((row) => row.rowId !== rowId))
    },
    [onChange],
  )

  const pick = useCallback((rowId: string) => {
    setDetailed(false)
    setPicked(rowId)
  }, [])

  const move = useCallback(
    (rowId: string, by: number) => {
      onChange((current) => {
        const order = current.filter((row) => row.direction === direction)
        const from = order.findIndex((row) => row.rowId === rowId)
        const to = from + by
        if (to < 0 || to >= order.length) return current
        const reordered = [...order]
        const [moved] = reordered.splice(from, 1)
        reordered.splice(to, 0, moved)
        return [...current.filter((row) => row.direction !== direction), ...reordered]
      })
    },
    [direction, onChange],
  )

  const add = () => {
    const row = emptyFieldRow(direction)
    onChange((current) => [...current, row])
    // Adding into a collapsed section would otherwise do nothing a user can see.
    setOpen(true)
    pick(row.rowId)
  }

  return (
    <Stack spacing={1}>
      <Stack direction="row" alignItems="center" justifyContent="space-between">
        <Button
          size="small"
          color="inherit"
          startIcon={<Iconify name={open ? 'collapse' : 'expand'} />}
          onClick={() => setOpen((current) => !current)}
          sx={{ px: 0 }}
        >
          <Typography variant="subtitle2">
            {isRequest ? t('operation.request_fields') : t('operation.response_fields')}
          </Typography>
          <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1 }}>
            {mine.length}
          </Typography>
        </Button>
        {!readOnly && (
          <Button size="small" startIcon={<Iconify name="add" />} onClick={add}>
            {tCommon('actions.add')}
          </Button>
        )}
      </Stack>

      <Collapse in={open} unmountOnExit>
        {mine.length === 0 ? (
          <Alert severity="info" icon={<Iconify name="info" />}>
            {isRequest ? t('field.no_request_rows') : t('field.no_response_rows')}
          </Alert>
        ) : (
          <Table size="small" sx={{ tableLayout: 'fixed' }}>
            <TableHead>
              <TableRow>
                <TableCell sx={{ width: COLUMN_WIDTH.key }}>
                  <ClippedText text={t('field.key')} />
                </TableCell>
                <TableCell sx={{ width: COLUMN_WIDTH.location }}>
                  <ClippedText text={t('field.location')} />
                </TableCell>
                <TableCell sx={{ width: COLUMN_WIDTH.wirePath }}>
                  <ClippedText text={t('field.wire_path')} />
                </TableCell>
                {isRequest && (
                  <Fragment>
                    <TableCell sx={{ width: COLUMN_WIDTH.valueSource }}>
                      <ClippedText text={t('field.value_source')} />
                    </TableCell>
                    <TableCell sx={{ width: COLUMN_WIDTH.value }}>
                      <ClippedText text={t('field.value')} />
                    </TableCell>
                  </Fragment>
                )}
                <TableCell align="right" sx={{ width: COLUMN_WIDTH.actions }} />
              </TableRow>
            </TableHead>
            <TableBody>
              {mine.map((row, index) =>
                row.rowId === picked && !readOnly ? (
                  <FieldRowEditor
                    key={row.rowId}
                    row={row}
                    index={index}
                    rowCount={mine.length}
                    secretNames={secretNames}
                    pathTemplate={pathTemplate}
                    detailed={detailed}
                    onToggleDetails={() => setDetailed((current) => !current)}
                    onPatch={patch}
                    onMove={move}
                    onDone={() => setPicked(null)}
                  />
                ) : (
                  <FieldRowText
                    key={row.rowId}
                    row={row}
                    issues={issuesByRow.get(row.rowId) ?? ''}
                    onPick={readOnly ? undefined : pick}
                    onRemove={readOnly ? undefined : remove}
                    editLabel={tCommon('actions.edit')}
                    deleteLabel={tCommon('actions.delete')}
                  />
                ),
              )}
            </TableBody>
          </Table>
        )}
      </Collapse>
    </Stack>
  )
}

/** What the server would reject about one row, in the row's own words. */
function rowIssues(row: FieldRow, pathTemplate: string): string[] {
  const issues: string[] = []
  if (row.key.trim() === '') issues.push('key')
  if (row.wire_path.trim() === '') issues.push('wire_path')
  // The server stores ONE_OF with no list; the rule it declares can then never hold.
  if (row.match_mode === 'ONE_OF' && (row.expected_values ?? []).length === 0) {
    issues.push('expected_values')
  }
  if (row.direction === 'REQUEST') {
    if (row.value_source === 'LITERAL' && String(row.value ?? '') === '') issues.push('value')
    if (row.value_source === 'SECRET' && (row.secret_name ?? '') === '') issues.push('secret')
    if (
      PLACEHOLDER_LOCATIONS.includes(row.location) &&
      row.key.trim() !== '' &&
      !pathTemplate.includes(`{${row.key}}`)
    ) {
      issues.push(`{${row.key}}`)
    }
  }
  return issues
}

/**
 * Every issue, named by the row it belongs to. One save carries the whole array
 * and a bare 422 gives no row back, so the numbering is per direction — the way
 * the row is counted on screen.
 */
export function fieldIssues(rows: FieldRow[], pathTemplate: string): string[] {
  const issues: string[] = []
  const position = new Map<FieldDirection, number>()
  const keys = new Map<string, number>()

  for (const row of rows) {
    const index = (position.get(row.direction) ?? 0) + 1
    position.set(row.direction, index)
    const at = `${row.direction} #${index}`

    for (const issue of rowIssues(row, pathTemplate)) issues.push(`${at}: ${issue}`)

    if (row.key.trim() !== '') {
      const identity = `${row.direction}:${row.key}`
      const first = keys.get(identity)
      if (first === undefined) keys.set(identity, index)
      else issues.push(`${at}: duplicate of #${first}`)
    }
  }

  /**
   * The converse of the per-row check, and the one that was missing: a template
   * segment nobody declares. Measured — `/api/items/{item_id}` with the field's
   * location left at `QUERY` saved without a word, and the run answered "외부 API
   * 호출이 실패했습니다" because the literal `{item_id}` went out on the wire. The
   * check is here rather than per row because no row owns a placeholder that has
   * no row.
   */
  const declared = new Set(
    rows
      .filter((row) => row.direction === 'REQUEST' && PLACEHOLDER_LOCATIONS.includes(row.location))
      .map((row) => row.key.trim()),
  )
  for (const [, name] of pathTemplate.matchAll(/\{([^{}]+)\}/g)) {
    if (!declared.has(name)) issues.push(`{${name}}`)
  }

  return issues
}


/**
 * A comma-separated list as the server's array.
 *
 * Chips would be the richer control and the wrong trade here: this list is two or
 * three media types typed once, and a chip editor adds a second way to be
 * half-committed — a value typed but not yet turned into a chip. Empty means the
 * field carries no list at all, which is `null`, not `[]`: an empty array would
 * declare "match one of nothing".
 */
function parseExpectedValues(text: string): string[] | null {
  const values = text
    .split(',')
    .map((value) => value.trim())
    .filter((value) => value !== '')
  return values.length === 0 ? null : values
}

interface FieldRowTextProps {
  row: FieldRow
  /** Its verdict, already computed: `''` when the row is fine. */
  issues: string
  /** Absent while reading: the row is then text with nothing to press. */
  onPick?: (rowId: string) => void
  onRemove?: (rowId: string) => void
  editLabel: string
  deleteLabel: string
}

/**
 * A row at rest. Memoised on its own row, so typing in the picked row does not
 * re-render the other two hundred.
 */
const FieldRowText = memo(function FieldRowText({
  row,
  issues,
  onPick,
  onRemove,
  editLabel,
  deleteLabel,
}: FieldRowTextProps) {
  const isRequest = row.direction === 'REQUEST'
  const tone = issues === '' ? undefined : 'error.main'

  return (
    <TableRow sx={{ height: READ_ROW_HEIGHT }}>
      <TableCell title={issues === '' ? undefined : issues} sx={{ color: tone }}>
        <ClippedText text={row.key === '' ? '—' : row.key} />
      </TableCell>
      <TableCell>
        <ClippedText text={row.location} />
      </TableCell>
      <TableCell sx={{ color: tone }}>
        <ClippedText text={row.wire_path === '' ? '—' : row.wire_path} />
      </TableCell>
      {isRequest && (
        <Fragment>
          <TableCell>
            <ClippedText text={row.value_source ?? ''} />
          </TableCell>
          <TableCell>
            <ClippedText
              text={
                row.value_source === 'LITERAL'
                  ? String(row.value ?? '')
                  : row.value_source === 'SECRET'
                    ? (row.secret_name ?? '')
                    : '—'
              }
            />
          </TableCell>
        </Fragment>
      )}
      <TableCell align="right" sx={{ px: 0 }}>
        {onPick !== undefined && onRemove !== undefined && (
          <RowActionButtons
            actions={[
              { label: editLabel, icon: 'edit', onClick: () => onPick(row.rowId) },
              {
                label: deleteLabel,
                icon: 'delete',
                tone: 'error',
                onClick: () => onRemove(row.rowId),
              },
            ]}
          />
        )}
      </TableCell>
    </TableRow>
  )
})

interface FieldRowEditorProps {
  row: FieldRow
  index: number
  rowCount: number
  secretNames: string[]
  pathTemplate: string
  detailed: boolean
  onToggleDetails: () => void
  onPatch: (rowId: string, next: Partial<FieldRow>) => void
  onMove: (rowId: string, by: number) => void
  onDone: () => void
}

/** The one row that is a form. */
function FieldRowEditor({
  row,
  index,
  rowCount,
  secretNames,
  pathTemplate,
  detailed,
  onToggleDetails,
  onPatch,
  onMove,
  onDone,
}: FieldRowEditorProps) {
  const { t } = useTranslation('integration')
  const { t: tCommon } = useTranslation('common')

  const isRequest = row.direction === 'REQUEST'
  const locations = isRequest ? REQUEST_LOCATIONS : RESPONSE_LOCATIONS
  const pathMismatch =
    isRequest &&
    PLACEHOLDER_LOCATIONS.includes(row.location) &&
    row.key !== '' &&
    !pathTemplate.includes(`{${row.key}}`)
  const columnCount = isRequest ? 6 : 4

  return (
    <Fragment>
      <TableRow sx={{ height: EDIT_ROW_HEIGHT, ...EDITING_ROW_SX }}>
        <TableCell>
          <TextField
            value={row.key}
            onChange={(event) => onPatch(row.rowId, { key: event.target.value })}
            size="small"
            fullWidth
            autoFocus
            placeholder={t('field.key')}
            error={row.key.trim() === ''}
          />
        </TableCell>

        <TableCell>
          <TextField
            select
            value={row.location}
            onChange={(event) =>
              onPatch(row.rowId, { location: event.target.value as FieldLocation })
            }
            size="small"
            fullWidth
          >
            {locations.map((location) => (
              <MenuItem key={location} value={location}>
                {location}
              </MenuItem>
            ))}
          </TextField>
        </TableCell>

        <TableCell>
          <TextField
            value={row.wire_path}
            onChange={(event) => onPatch(row.rowId, { wire_path: event.target.value })}
            size="small"
            fullWidth
            placeholder={
              PLACEHOLDER_LOCATIONS.includes(row.location)
                ? `{${row.key === '' ? 'key' : row.key}}`
                : '/body/items'
            }
            error={row.wire_path.trim() === '' || pathMismatch}
            helperText={pathMismatch ? t('field.path_missing') : undefined}
          />
        </TableCell>

        {isRequest && (
          <Fragment>
            <TableCell>
              <TextField
                select
                value={row.value_source ?? 'CALLER'}
                onChange={(event) =>
                  onPatch(row.rowId, {
                    value_source: event.target.value as RequestValueSource,
                    value: null,
                    secret_name: null,
                  })
                }
                size="small"
                fullWidth
              >
                {VALUE_SOURCES.map((source) => (
                  <MenuItem key={source} value={source}>
                    {source}
                  </MenuItem>
                ))}
              </TextField>
            </TableCell>

            <TableCell>
              {row.value_source === 'LITERAL' ? (
                <TextField
                  value={String(row.value ?? '')}
                  onChange={(event) => onPatch(row.rowId, { value: event.target.value })}
                  size="small"
                  fullWidth
                  error={String(row.value ?? '') === ''}
                />
              ) : row.value_source === 'SECRET' ? (
                <TextField
                  select
                  value={row.secret_name ?? ''}
                  onChange={(event) => onPatch(row.rowId, { secret_name: event.target.value })}
                  size="small"
                  fullWidth
                  error={(row.secret_name ?? '') === ''}
                >
                  {secretNames.map((name) => (
                    <MenuItem key={name} value={name}>
                      {name}
                    </MenuItem>
                  ))}
                </TextField>
              ) : (
                <Typography variant="caption" color="text.secondary">
                  {row.value_source === 'CALLER'
                    ? t('field.supplied_by_caller')
                    : t('field.supplied_by_server')}
                </Typography>
              )}
            </TableCell>
          </Fragment>
        )}

        <TableCell align="right" sx={{ px: 0 }}>
          <Stack direction="row" justifyContent="flex-end">
            <IconButton size="small" aria-label={t('field.more')} onClick={onToggleDetails}>
              <Iconify name={detailed ? 'collapse' : 'expand'} />
            </IconButton>
            <IconButton size="small" aria-label={tCommon('actions.close')} onClick={onDone}>
              <Iconify name="check" />
            </IconButton>
          </Stack>
        </TableCell>
      </TableRow>

      {detailed && (
        <TableRow sx={EDITING_ROW_SX}>
          <TableCell colSpan={columnCount} sx={{ py: 0, border: 'none' }}>
            <Collapse in appear>
              <Stack spacing={2} sx={{ py: 2 }}>
                <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
                  <TextField
                    select
                    label={t('field.value_type')}
                    value={row.value_type}
                    onChange={(event) =>
                      onPatch(row.rowId, { value_type: event.target.value as ValueType })
                    }
                    size="small"
                    sx={{ width: ADVANCED_FIELD_WIDTH }}
                  >
                    {VALUE_TYPES.map((type) => (
                      <MenuItem key={type} value={type}>
                        {type}
                      </MenuItem>
                    ))}
                  </TextField>

                  <TextField
                    label={t('field.format')}
                    value={row.format ?? ''}
                    onChange={(event) =>
                      onPatch(row.rowId, {
                        format: event.target.value === '' ? null : event.target.value,
                      })
                    }
                    size="small"
                    sx={{ width: ADVANCED_FIELD_WIDTH }}
                    placeholder="YYYYMMDD"
                  />

                  {row.location === 'HEADER' && (
                    <TextField
                      select
                      label={t('field.match_mode')}
                      value={row.match_mode ?? 'IGNORE'}
                      onChange={(event) =>
                        onPatch(row.rowId, { match_mode: event.target.value as HeaderMatchMode })
                      }
                      size="small"
                      sx={{ width: ADVANCED_FIELD_WIDTH }}
                    >
                      {MATCH_MODES.map((mode) => (
                        <MenuItem key={mode} value={mode}>
                          {mode}
                        </MenuItem>
                      ))}
                    </TextField>
                  )}

                  {row.location === 'HEADER' && row.match_mode === 'ONE_OF' && (
                    <TextField
                      label={t('field.expected_values')}
                      value={(row.expected_values ?? []).join(', ')}
                      onChange={(event) =>
                        onPatch(row.rowId, { expected_values: parseExpectedValues(event.target.value) })
                      }
                      size="small"
                      sx={{ minWidth: ADVANCED_FIELD_WIDTH * 2 }}
                      placeholder="application/json, text/json"
                      error={(row.expected_values ?? []).length === 0}
                      helperText={
                        (row.expected_values ?? []).length === 0
                          ? t('field.expected_values_hint')
                          : undefined
                      }
                    />
                  )}
                </Stack>

                <TextField
                  label={t('field.description')}
                  value={row.description ?? ''}
                  onChange={(event) =>
                    onPatch(row.rowId, {
                      description: event.target.value === '' ? null : event.target.value,
                    })
                  }
                  size="small"
                  fullWidth
                  placeholder={t('field.description_hint')}
                />

                {/* useFlexGap: the segment-order group below pushes itself right
                    with `ml: 'auto'`, which a margin-spaced Stack overrides. */}
                <Stack direction="row" spacing={2} alignItems="center" useFlexGap>
                  <FormControlLabel
                    control={
                      <Switch
                        size="small"
                        checked={row.required}
                        onChange={(event) => onPatch(row.rowId, { required: event.target.checked })}
                      />
                    }
                    label={t('field.required')}
                  />
                  <FormControlLabel
                    control={
                      <Switch
                        size="small"
                        checked={row.sensitive ?? false}
                        onChange={(event) => onPatch(row.rowId, { sensitive: event.target.checked })}
                      />
                    }
                    label={t('field.sensitive')}
                  />
                  <FormControlLabel
                    control={
                      <Switch
                        size="small"
                        checked={row.enabled ?? true}
                        onChange={(event) => onPatch(row.rowId, { enabled: event.target.checked })}
                      />
                    }
                    label={t('form.enabled')}
                  />

                  {row.location === 'PATH_QUERY' && (
                    <Stack direction="row" alignItems="center" spacing={0.5} sx={{ ml: 'auto' }}>
                      <Typography variant="caption" color="text.secondary">
                        {t('field.segment_order')}
                      </Typography>
                      <IconButton
                        size="small"
                        aria-label={t('field.move_up')}
                        disabled={index === 0}
                        onClick={() => onMove(row.rowId, -1)}
                      >
                        <Iconify name="collapse" />
                      </IconButton>
                      <IconButton
                        size="small"
                        aria-label={t('field.move_down')}
                        disabled={index === rowCount - 1}
                        onClick={() => onMove(row.rowId, 1)}
                      >
                        <Iconify name="expand" />
                      </IconButton>
                    </Stack>
                  )}
                </Stack>
              </Stack>
            </Collapse>
          </TableCell>
        </TableRow>
      )}
    </Fragment>
  )
}
