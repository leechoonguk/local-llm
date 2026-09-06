/**
 * One operation: the same panel reads it and edits it.
 *
 * Two screens for one record was the shape this replaced — a read-only detail
 * panel plus an edit form, differing only in which mode the door landed in. The
 * record has one surface: reading renders text, editing turns the same rows into
 * inputs, and the pinned strip carries both modes' verbs.
 *
 * Editing is this panel's own state, never a route: pressing edit while reading
 * changes the surface in place, and the record stays scrolled where it was.
 * Cancelling returns to reading the same record, restoring the form from the
 * record it was given, so a dropped copy can never be mistaken for saved state.
 */

import { Fragment, useState } from 'react'
import { Alert, Button, Divider, FormControlLabel, Stack, Switch, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import DetailField from '@/components/detail/DetailField'
import PanelStrip from '@/components/detail/PanelStrip'
import { ChoiceField, NumberField, ScalarField } from '@/components/detail/RecordFields'
import Iconify from '@/components/iconify/Iconify'
import Label from '@/components/label/Label'
import { applyServerError } from '@/lib/api/formErrors'
import { useUpdateIntegration } from '@/lib/api/hooks/useIntegration'
import { useToast } from '@/hooks/useToast'
import IntegrationOperationFieldsEditor, {
  emptyFieldRow,
  fieldIssues,
} from '@/sections/integration/IntegrationOperationFieldsEditor'
import type { FieldRow } from '@/sections/integration/IntegrationOperationFieldsEditor'
import type {
  HttpMethod,
  Integration,
  IntegrationOperation,
  IntegrationOperationCreateRequest,
  ResponseFormat,
} from '@/types/integration'

const METHODS: HttpMethod[] = ['GET', 'HEAD', 'OPTIONS', 'POST', 'PUT', 'PATCH', 'DELETE']

const RESPONSE_FORMATS: ResponseFormat[] = ['JSON', 'XML']

/** `gt=0` on the server: a zero timeout is refused, and 0 is what an emptied input gives. */
const MIN_TIMEOUT_MS = 1

/** `max_length` on `IntegrationOperationCreateRequest`. */
const CODE_MAX_LENGTH = 64

const PATH_TEMPLATE_MAX_LENGTH = 2048

const RESPONSE_ROOT_MAX_LENGTH = 512

/** The server rejects a code that is not lowercase letters, digits and hyphens. */
const CODE_PATTERN = /^[a-z0-9-]+$/

const DEFAULTS = {
  connect_timeout_ms: 5000,
  read_timeout_ms: 15000,
  max_retries: 2,
  retry_base_ms: 200,
  retry_max_ms: 2000,
}

/**
 * Shapes, shown in the field instead of under it. A placeholder says what a value
 * looks like exactly while the field is empty, and leaves when it is not — which
 * is the whole life of a hint.
 */
const PATH_EXAMPLE = '/1471000/{service}/json/{start}/{end}'

const RESPONSE_ROOT_EXAMPLE = '/body/items'

// Sixteen `CODE=seconds` pairs of up to twenty-four characters, comma-separated.
const QUOTA_CODES_MAX_LENGTH = 16 * 25
const QUOTA_CODES_EXAMPLE = 'INFO-320=3600, INFO-500=60'

interface IntegrationOperationPanelProps {
  provider: Integration
  /** `null` creates: an operation reads or edits that one. */
  operation: IntegrationOperation | null
  /** An existing operation can be run from its own panel. */
  onRun: () => void
  onBack: () => void
}

export default function IntegrationOperationPanel({
  provider,
  operation,
  onRun,
  onBack,
}: IntegrationOperationPanelProps) {
  const { t } = useTranslation('integration')
  const { t: tCommon } = useTranslation('common')
  const toast = useToast()
  const update = useUpdateIntegration()
  /** A new operation has nothing to read, so it starts editing. */
  const [editing, setEditing] = useState(operation === null)
  const [form, setForm] = useState(() => initialForm(operation))
  const [fields, setFields] = useState<FieldRow[]>(() => initialFields(operation))
  const [failure, setFailure] = useState<string | null>(null)

  const readOnly = !editing
  const invalidCode = !CODE_PATTERN.test(form.code)
  const duplicate =
    operation === null && provider.operations.some((existing) => existing.code === form.code)
  const mappingIssues = fieldIssues(fields, form.path_template)
  const blocked =
    update.isPending ||
    form.code === '' ||
    form.path_template === '' ||
    invalidCode ||
    duplicate ||
    mappingIssues.length > 0

  const save = async () => {
    setFailure(null)
    try {
      await update.mutateAsync({
        id: provider.id,
        data: { operations: nextOperations(provider, operation, form, fields) },
      })
      toast.success(tCommon('messages.saved'))
      // A saved edit leaves the record open, reading: returning to the table threw
      // away the place the work happened, and the next thing a person does after
      // saving one field is usually looking at the next one.
      if (operation === null) onBack()
      else setEditing(false)
    } catch (error) {
      applyServerError(error, {
        t: tCommon,
        setError: () => setFailure(null),
        toastError: (message: string) => setFailure(message),
      })
    }
  }

  /** Cancelling an edit returns to reading the same record, not to the list. */
  const cancelEdit = () => {
    if (operation === null) {
      onBack()
      return
    }
    setForm(initialForm(operation))
    setFields(initialFields(operation))
    setFailure(null)
    setEditing(false)
  }

  return (
    <Stack spacing={2}>
      <PanelStrip
        onBack={onBack}
        actions={
          readOnly && operation !== null ? (
            <Fragment>
              <Button
                size="small"
                color="inherit"
                startIcon={<Iconify name="run" />}
                onClick={onRun}
              >
                {t('execute.run')}
              </Button>
              <Button
                size="small"
                color="inherit"
                startIcon={<Iconify name="edit" />}
                onClick={() => setEditing(true)}
              >
                {tCommon('actions.edit')}
              </Button>
            </Fragment>
          ) : (
            <Fragment>
              <Button size="small" variant="contained" onClick={() => void save()} disabled={blocked}>
                {tCommon('actions.save')}
              </Button>
              <Button size="small" color="inherit" onClick={cancelEdit}>
                {tCommon('actions.cancel')}
              </Button>
            </Fragment>
          )
        }
      >
        <Typography variant="subtitle2">
          {operation === null ? t('operation.create_title') : operation.code}
        </Typography>
        {operation !== null && <Label color="info">{operation.method}</Label>}
      </PanelStrip>

      <Divider sx={{ borderStyle: 'dashed' }} />

      {/*
       * Under the strip, not at the end of the body: these two are the reason the
       * pinned save is dead, and a reason below the fold is a reason nobody reads.
       * Measured — 22 response fields put the warning off-screen while the disabled
       * button stayed in view.
       */}
      {editing && mappingIssues.length > 0 && (
        <Alert severity="warning">{mappingIssues.slice(0, 3).join(' · ')}</Alert>
      )}

      {failure !== null && <Alert severity="error">{failure}</Alert>}

      <Stack spacing={2}>
        <ScalarField
          label={t('operation.code')}
          value={form.code}
          maxLength={CODE_MAX_LENGTH}
          readOnly={readOnly}
          // Immutable, and still a value the reader needs: `readOnly`, never
          // `disabled`. A disabled control is exempt from WCAG's contrast rules and
          // is skipped by screen readers and by Tab — the code is what the server
          // keeps unique per provider, so it stays legible and reachable.
          immutable={operation !== null}
          error={editing && form.code !== '' && (invalidCode || duplicate)}
          helperText={
            duplicate
              ? t('operation.duplicate_code')
              : form.code !== '' && invalidCode
                ? tCommon('errors.provider_code_invalid')
                : undefined
          }
          onChange={(value) => setForm({ ...form, code: value })}
        />

        <Stack direction="row" spacing={2}>
          <ChoiceField
            label={t('operation.method')}
            value={form.method}
            options={METHODS}
            readOnly={readOnly}
            onChange={(value) => setForm({ ...form, method: value as HttpMethod })}
          />
          <ScalarField
            label={t('operation.path_template')}
            value={form.path_template}
            readOnly={readOnly}
            maxLength={PATH_TEMPLATE_MAX_LENGTH}
            placeholder={PATH_EXAMPLE}
            onChange={(value) => setForm({ ...form, path_template: value })}
          />
        </Stack>

        <Stack direction="row" spacing={2}>
          <ChoiceField
            label={t('operation.response_format')}
            value={form.response_format}
            options={RESPONSE_FORMATS}
            readOnly={readOnly}
            onChange={(value) => setForm({ ...form, response_format: value as ResponseFormat })}
          />
          <ScalarField
            label={t('operation.response_root')}
            value={form.response_root}
            readOnly={readOnly}
            maxLength={RESPONSE_ROOT_MAX_LENGTH}
            placeholder={RESPONSE_ROOT_EXAMPLE}
            onChange={(value) => setForm({ ...form, response_root: value })}
          />
        </Stack>

        {/*
         * The envelope values that mean "not this key right now" rather than
         * "this answer is wrong", each with the seconds the key sits out: the
         * client sends the next member of the key's rotation group on one of
         * these. Typed as one line - a portal has one or two, and a table
         * editor for two codes is a second surface.
         */}
        <ScalarField
          label={t('operation.quota_codes')}
          value={form.quota_codes}
          readOnly={readOnly}
          maxLength={QUOTA_CODES_MAX_LENGTH}
          placeholder={QUOTA_CODES_EXAMPLE}
          helperText={readOnly ? undefined : t('operation.quota_codes_hint')}
          onChange={(value) => setForm({ ...form, quota_codes: value })}
        />

        <Stack direction="row" spacing={2}>
          <NumberField
            label={t('operation.connect_timeout')}
            value={form.connect_timeout_ms}
            readOnly={readOnly}
            min={MIN_TIMEOUT_MS}
            onChange={(value) => setForm({ ...form, connect_timeout_ms: value })}
          />
          <NumberField
            label={t('operation.read_timeout')}
            value={form.read_timeout_ms}
            readOnly={readOnly}
            min={MIN_TIMEOUT_MS}
            onChange={(value) => setForm({ ...form, read_timeout_ms: value })}
          />
          <NumberField
            label={t('operation.max_retries')}
            value={form.max_retries}
            readOnly={readOnly}
            onChange={(value) => setForm({ ...form, max_retries: value })}
          />
        </Stack>

        {/*
         * Reading, a flag is the badge the tables use for it — a disabled switch is
         * a control the reader has to decode, and it is the same state either way.
         */}
        {readOnly ? (
          <Stack direction="row" spacing={3}>
            <DetailField label={t('operation.idempotent')}>
              <Label variant="soft" color={form.idempotent ? 'success' : 'default'}>
                {form.idempotent ? tCommon('status.enabled') : tCommon('status.disabled')}
              </Label>
            </DetailField>
            <DetailField label={t('form.enabled')}>
              <Label variant="soft" color={form.enabled ? 'success' : 'default'}>
                {form.enabled ? tCommon('status.enabled') : tCommon('status.disabled')}
              </Label>
            </DetailField>
          </Stack>
        ) : (
          <Stack direction="row" spacing={3}>
            <FormControlLabel
              control={
                <Switch
                  checked={form.idempotent}
                  onChange={(event) => setForm({ ...form, idempotent: event.target.checked })}
                />
              }
              label={t('operation.idempotent')}
            />
            <FormControlLabel
              control={
                <Switch
                  checked={form.enabled}
                  onChange={(event) => setForm({ ...form, enabled: event.target.checked })}
                />
              }
              label={t('form.enabled')}
            />
          </Stack>
        )}
      </Stack>

      <IntegrationOperationFieldsEditor
        direction="REQUEST"
        rows={fields}
        secretNames={provider.secrets.map((secret) => secret.name)}
        pathTemplate={form.path_template}
        onChange={setFields}
        readOnly={readOnly}
      />

      <IntegrationOperationFieldsEditor
        direction="RESPONSE"
        rows={fields}
        secretNames={provider.secrets.map((secret) => secret.name)}
        pathTemplate={form.path_template}
        onChange={setFields}
        readOnly={readOnly}
      />
    </Stack>
  )
}

type OperationForm = ReturnType<typeof initialForm>

function initialForm(operation: IntegrationOperation | null) {
  return {
    code: operation?.code ?? '',
    method: (operation?.method ?? 'GET') as HttpMethod,
    path_template: operation?.path_template ?? '',
    response_format: operation?.response_format ?? 'JSON',
    response_root: operation?.response_root ?? '',
    connect_timeout_ms: operation?.connect_timeout_ms ?? DEFAULTS.connect_timeout_ms,
    read_timeout_ms: operation?.read_timeout_ms ?? DEFAULTS.read_timeout_ms,
    max_retries: operation?.max_retries ?? DEFAULTS.max_retries,
    retry_base_ms: operation?.retry_base_ms ?? DEFAULTS.retry_base_ms,
    retry_max_ms: operation?.retry_max_ms ?? DEFAULTS.retry_max_ms,
    idempotent: operation?.idempotent ?? true,
    quota_codes: joinCodes(operation?.quota_codes ?? {}),
    enabled: operation?.enabled ?? true,
  }
}

/**
 * The rows the editor starts from. An existing operation's fields keep their
 * stored order; a new operation starts empty rather than with a guessed row,
 * because a guess would be saved as a declaration.
 */
function initialFields(operation: IntegrationOperation | null): FieldRow[] {
  return [...(operation?.fields ?? [])]
    .sort((left, right) => left.ordinal - right.ordinal)
    .map((field, index) => ({ ...toFieldRequest(field), rowId: `stored-${index}-${field.id}` }))
}

/** Kept beside `initialFields` so a new row's shape has one definition. */
export const newFieldRow = emptyFieldRow

/**
 * The whole array the server will store: the edited member replaced (or added),
 * every other one sent back exactly as it arrived.
 */
/** `rowId` is the editor's own handle: it never goes on the wire. */
function stripRowId(row: FieldRow) {
  const wire: Record<string, unknown> = { ...row }
  delete wire.rowId
  return wire as Omit<FieldRow, 'rowId'>
}

function nextOperations(
  provider: Integration,
  editing: IntegrationOperation | null,
  form: OperationForm,
  fields: FieldRow[],
): IntegrationOperationCreateRequest[] {
  const edited: IntegrationOperationCreateRequest = {
    code: form.code,
    method: form.method,
    path_template: form.path_template,
    request_media_type: editing?.request_media_type ?? null,
    response_format: form.response_format,
    response_root: form.response_root === '' ? null : form.response_root,
    connect_timeout_ms: form.connect_timeout_ms,
    read_timeout_ms: form.read_timeout_ms,
    max_retries: form.max_retries,
    retry_base_ms: form.retry_base_ms,
    retry_max_ms: form.retry_max_ms,
    idempotent: form.idempotent,
    request_schema: editing?.request_schema ?? null,
    quota_codes: splitCodes(form.quota_codes),
    enabled: form.enabled,
    // Ordinal is row order: the arrows in the editor move it, and the server reads
    // it to build the path's segments and the query string.
    fields: fields.map((field, index) => ({ ...stripRowId(field), ordinal: index })),
  }

  const others = provider.operations
    .filter((existing) => existing.id !== editing?.id)
    .map(toOperationRequest)

  return [...others, edited]
}

/** One line of `CODE=seconds` pairs to the object the server stores. */
function splitCodes(line: string): Record<string, number> {
  const codes: Record<string, number> = {}
  for (const pair of line.split(',')) {
    const [code, seconds] = pair.split('=').map((part) => part.trim())
    const parsed = Number(seconds)
    if (code !== '' && Number.isInteger(parsed) && parsed > 0) codes[code] = parsed
  }
  return codes
}

function joinCodes(codes: Record<string, number>): string {
  return Object.entries(codes)
    .map(([code, seconds]) => `${code}=${seconds}`)
    .join(', ')
}

export function toOperationRequest(
  operation: IntegrationOperation,
): IntegrationOperationCreateRequest {
  return {
    code: operation.code,
    method: operation.method as HttpMethod,
    path_template: operation.path_template,
    request_media_type: operation.request_media_type,
    response_format: operation.response_format,
    response_root: operation.response_root,
    connect_timeout_ms: operation.connect_timeout_ms,
    read_timeout_ms: operation.read_timeout_ms,
    max_retries: operation.max_retries,
    retry_base_ms: operation.retry_base_ms,
    retry_max_ms: operation.retry_max_ms,
    idempotent: operation.idempotent,
    request_schema: operation.request_schema,
    // Every sibling travels with the edited one, so a field left out here is a
    // field the save silently resets - the seed's quota code included.
    quota_codes: operation.quota_codes,
    enabled: operation.enabled,
    fields: operation.fields.map(toFieldRequest),
  }
}

function toFieldRequest(field: IntegrationOperation['fields'][number]) {
  return {
    direction: field.direction,
    location: field.location,
    key: field.key,
    wire_path: field.wire_path,
    value_source: field.value_source,
    value: field.value,
    secret_name: field.secret_name,
    value_type: field.value_type,
    format: field.format,
    required: field.required,
    description: field.description,
    sensitive: field.sensitive,
    ordinal: field.ordinal,
    enabled: field.enabled,
    match_mode: field.match_mode,
    expected_values: field.expected_values,
  }
}
