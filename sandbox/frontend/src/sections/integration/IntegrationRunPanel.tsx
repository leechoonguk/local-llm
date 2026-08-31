/**
 * The operation console — a panel inside the provider dialog, not a dialog.
 *
 * One modal is the rule, and it buys more than tidiness: a console stacked on a
 * detail dialog hid the record it belonged to, and closing it dropped the result
 * with no way back. As a panel the provider header stays visible, the result
 * stays until the operator navigates away from it, and "back" is a button rather
 * than a dismissed layer.
 *
 * The form is generated from the operation's own configuration: every REQUEST
 * field whose `value_source` is `CALLER`, ordered by `ordinal`. A SECRET-sourced
 * field never appears — the server resolves it, and a screen asking for it would
 * be asking an operator to paste a credential into a browser.
 */

import { useMemo, useState } from 'react'
import { Alert, Box, Button, Divider, Stack, TextField, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import Iconify from '@/components/iconify/Iconify'
import PanelStrip from '@/components/detail/PanelStrip'
import Label from '@/components/label/Label'
import { serverErrorMessage } from '@/lib/api/formErrors'
import { toApiError } from '@/lib/api/errors'
import { useExecuteOperation } from '@/lib/api/hooks/useIntegration'
import type { UpstreamResponse } from '@/types/api'
import type {
  IntegrationExecuteResponse,
  IntegrationField,
  IntegrationOperation,
} from '@/types/integration'

/**
 * What one run ended as: the provider answered, or it refused and said why.
 *
 * One value rather than two states. With the mutation's `data` holding the
 * success and a separate failure state holding the refusal, a failed re-run left
 * the previous success on screen underneath the new error.
 */
type RunOutcome =
  | { ok: true; result: IntegrationExecuteResponse }
  | { ok: false; reason: string; upstream: UpstreamResponse | null }

/** A payload block is read, not skimmed: give it room and let it scroll. */
const PAYLOAD_MAX_HEIGHT = 220

const JSON_INDENT = 2

interface IntegrationRunPanelProps {
  integrationId: string
  operation: IntegrationOperation
  onBack: () => void
}

export default function IntegrationRunPanel({
  integrationId,
  operation,
  onBack,
}: IntegrationRunPanelProps) {
  const { t } = useTranslation('integration')
  const { t: tCommon } = useTranslation('common')
  const execute = useExecuteOperation(integrationId)
  const [values, setValues] = useState<Record<string, string>>({})
  // One run has one ending, so it is one value and one section on screen. Split
  // in two - the mutation's `data` for a success, a separate failure state under
  // the strip - the same three blocks (status, then payload) were written twice
  // and the panel showed a stale success beside a fresh failure.
  const [outcome, setOutcome] = useState<RunOutcome | null>(null)

  const inputs = useMemo(() => callerFields(operation), [operation])
  const missing = inputs.some((field) => field.required && (values[field.key] ?? '').trim() === '')

  const run = async () => {
    setOutcome(null)
    try {
      const result = await execute.mutateAsync({
        operation: operation.code,
        data: { inputs: toInputs(inputs, values) },
      })
      setOutcome({ ok: true, result })
    } catch (error) {
      const apiError = toApiError(error)
      setOutcome({
        ok: false,
        // `reason` and not `message`: this string is already translated from the
        // error code, and a field named after the server's own key reads like
        // the server's own text - which must never reach a screen.
        reason: serverErrorMessage(apiError.code, tCommon),
        upstream: apiError.upstream,
      })
    }
  }

  return (
    <Stack spacing={2}>
      <PanelStrip
        onBack={onBack}
        actions={
          <Button
            size="small"
            variant="contained"
            startIcon={<Iconify name="run" />}
            onClick={() => void run()}
            disabled={execute.isPending || missing}
          >
            {t('execute.run')}
          </Button>
        }
      >
        <Label color="info">{operation.method}</Label>
        <Typography variant="subtitle2">{operation.code}</Typography>
        <Typography variant="body2" color="text.secondary" noWrap>
          {operation.path_template}
        </Typography>
      </PanelStrip>

      {/* The verdict sentence stays here, next to the button that is now dead:
          it is the reason, not the response. The response itself is one section
          at the bottom, the same one either way. */}
      {outcome !== null && !outcome.ok && <Alert severity="error">{outcome.reason}</Alert>}

      <Divider sx={{ borderStyle: 'dashed' }} />

      <Typography variant="subtitle2">{t('execute.inputs')}</Typography>
      {inputs.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          {t('execute.no_inputs')}
        </Typography>
      ) : (
        <Stack spacing={2}>
          {inputs.map((field) => (
            <TextField
              key={field.id}
              label={field.key}
              required={field.required}
              value={values[field.key] ?? ''}
              onChange={(event) =>
                setValues((previous) => ({ ...previous, [field.key]: event.target.value }))
              }
              // What the value is, in the field while it is empty. Under it, on
              // every input, it was a caption nobody reads twice — the field
              // tables already carry location and type.
              placeholder={field.description ?? field.value_type}
              size="small"
              fullWidth
            />
          ))}
        </Stack>
      )}

      {/* One result section for both endings: a run answered, and this is what it
          answered with. A failure that printed its response somewhere else was the
          same three blocks in a second place, above the inputs that produced it. */}
      {outcome !== null && (outcome.ok || outcome.upstream !== null) && (
        <Stack spacing={1}>
          <Divider sx={{ borderStyle: 'dashed' }} />
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Typography variant="subtitle2">{t('execute.result')}</Typography>
            <Label color={outcome.ok ? 'success' : 'error'}>
              {outcome.ok ? outcome.result.status_code : outcome.upstream?.status_code}
            </Label>
          </Stack>
          {outcome.ok ? (
            <>
              <Payload title={t('execute.payload')} value={outcome.result.canonical_payload} />
              <Payload title={t('execute.metadata')} value={outcome.result.metadata} />
            </>
          ) : (
            <Payload title={t('execute.upstream_body')} value={outcome.upstream?.body} />
          )}
        </Stack>
      )}
    </Stack>
  )
}

function Payload({ title, value }: { title: string; value: unknown }) {
  return (
    <Stack spacing={0.5}>
      <Typography variant="caption" color="text.secondary">
        {title}
      </Typography>
      <Box
        component="pre"
        sx={{
          m: 0,
          p: 1.5,
          typography: 'caption',
          bgcolor: 'background.paper',
          borderRadius: 1,
          maxHeight: PAYLOAD_MAX_HEIGHT,
          overflow: 'auto',
          // A provider's body arrives as one long line as often as not, and a
          // `pre` that only scrolls sideways hides the end of every line.
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {/* A provider's answer is already text. Stringifying it would print the
            escapes instead of the newlines that make it readable. */}
        {typeof value === 'string' ? value : JSON.stringify(value, null, JSON_INDENT)}
      </Box>
    </Stack>
  )
}

/** The fields the caller supplies: everything else the server resolves itself. */
function callerFields(operation: IntegrationOperation): IntegrationField[] {
  return operation.fields
    .filter((field) => field.direction === 'REQUEST' && field.value_source === 'CALLER')
    .sort((left, right) => left.ordinal - right.ordinal)
}

/**
 * Typed values, empty optionals dropped.
 *
 * An empty string is not "no value" on the wire — it is a value the provider
 * would filter on — so an untouched optional field must not be sent at all.
 */
function toInputs(
  fields: IntegrationField[],
  values: Record<string, string>,
): Record<string, unknown> {
  const inputs: Record<string, unknown> = {}
  for (const field of fields) {
    const raw = (values[field.key] ?? '').trim()
    if (raw === '') continue
    inputs[field.key] =
      field.value_type === 'INTEGER' || field.value_type === 'NUMBER' ? Number(raw) : raw
  }
  return inputs
}
