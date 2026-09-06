/**
 * The credential record — the operation panel's pattern applied to a secret.
 *
 * One surface reads and edits: reading renders `DetailField` text, editing turns
 * the same rows into inputs, and the pinned strip carries both modes' verbs. A
 * saved edit stays on the record; cancelling restores the form from the record it
 * was given.
 *
 * The value is the reason this screen is not the operation panel with different
 * labels. `IntegrationSecretReadResponse` has no `value` — the API never returns
 * a stored key — so:
 *
 *   reading   the value is a fixed mask. It says "a key is stored", and it is not
 *             a rendering of the key, because nothing can render one.
 *   editing   the input starts empty with the mask as its placeholder. Typing
 *             replaces the key; leaving it empty keeps the stored one, which is
 *             what the contract's optional `value` is for.
 *
 * The name is the address: `PUT /secrets/{name}` resolves the row, and every
 * `integration_field.secret_name` resolves through it. So it is `readOnly` while
 * editing an existing credential, never `disabled` — a disabled control is exempt
 * from contrast rules and skipped by both screen readers and Tab.
 */

import { Fragment, useState } from 'react'
import { Alert, Box, Button, Divider, FormControlLabel, Stack, Switch, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import DetailField from '@/components/detail/DetailField'
import { ScalarField } from '@/components/detail/RecordFields'
import Iconify from '@/components/iconify/Iconify'
import PanelStrip from '@/components/detail/PanelStrip'
import Label from '@/components/label/Label'
import { applyServerError } from '@/lib/api/formErrors'
import { useCreateSecret, useUpdateSecret } from '@/lib/api/hooks/useIntegration'
import { useToast } from '@/hooks/useToast'
import type { Integration, IntegrationSecret } from '@/types/integration'
import { formatDateTime } from '@/utils/formatTime'

/** The server never returns a stored value, so this stands for "a key is stored". */
const VALUE_MASK = '••••••••'

/** The server rejects a name longer than this (`IntegrationSecretCreateRequest`). */
const NAME_MAX_LENGTH = 64

const VALUE_MAX_LENGTH = 2048

const DESCRIPTION_MAX_LENGTH = 512

interface IntegrationSecretPanelProps {
  provider: Integration
  /** `null` creates; a secret reads or edits that one. */
  secret: IntegrationSecret | null
  onBack: () => void
}

export default function IntegrationSecretPanel({
  provider,
  secret,
  onBack,
}: IntegrationSecretPanelProps) {
  const { t } = useTranslation('integration')
  const { t: tCommon } = useTranslation('common')
  const toast = useToast()
  const create = useCreateSecret(provider.id)
  const update = useUpdateSecret(provider.id)

  const [editing, setEditing] = useState(secret === null)
  const [form, setForm] = useState(() => initialForm(secret))
  const [failure, setFailure] = useState<string | null>(null)

  const readOnly = !editing
  const pending = create.isPending || update.isPending
  const duplicate =
    secret === null && provider.secrets.some((existing) => existing.name === form.name)
  const missingValue = secret === null && form.value === ''
  const blocked = pending || form.name === '' || duplicate || missingValue

  const save = async () => {
    setFailure(null)
    try {
      if (secret === null) {
        await create.mutateAsync({
          name: form.name,
          value: form.value,
          description: form.description === '' ? null : form.description,
          enabled: form.enabled,
          rotation_group: form.rotationGroup === '' ? null : form.rotationGroup,
        })
        toast.success(tCommon('messages.saved'))
        onBack()
        return
      }
      await update.mutateAsync({
        name: secret.name,
        data: {
          // Only when the operator typed one: an empty box means "keep the stored key".
          value: form.value === '' ? undefined : form.value,
          description: form.description === '' ? null : form.description,
          enabled: form.enabled,
          // A group is set, never cleared, through this box: an empty box means
          // "keep it" - the same reading the value box has.
          rotation_group: form.rotationGroup === '' ? undefined : form.rotationGroup,
        },
      })
      toast.success(tCommon('messages.saved'))
      setForm((current) => ({ ...current, value: '' }))
      setEditing(false)
    } catch (error) {
      applyServerError(error, {
        t: tCommon,
        setError: () => setFailure(null),
        toastError: (message: string) => setFailure(message),
      })
    }
  }

  const cancelEdit = () => {
    if (secret === null) {
      onBack()
      return
    }
    setForm(initialForm(secret))
    setFailure(null)
    setEditing(false)
  }

  return (
    <Stack spacing={2}>
      <PanelStrip
        onBack={onBack}
        actions={
          readOnly && secret !== null ? (
            <Button
              size="small"
              color="inherit"
              startIcon={<Iconify name="edit" />}
              onClick={() => setEditing(true)}
            >
              {tCommon('actions.edit')}
            </Button>
          ) : (
            <Fragment>
              <Button
                size="small"
                variant="contained"
                onClick={() => void save()}
                disabled={blocked}
              >
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
          {secret === null ? t('secret.create_title') : secret.name}
        </Typography>
        {secret !== null && (
          <Label variant="soft" color={secret.enabled ? 'success' : 'default'}>
            {secret.enabled ? tCommon('status.enabled') : tCommon('status.disabled')}
          </Label>
        )}
      </PanelStrip>

      {/* Under the strip: a rejected save explains the button that rejected it. */}
      {failure !== null && <Alert severity="error">{failure}</Alert>}
      <Divider sx={{ borderStyle: 'dashed' }} />

      <Stack spacing={2}>
        <ScalarField
          label={t('secret.name')}
          value={form.name}
          readOnly={readOnly}
          immutable={secret !== null}
          maxLength={NAME_MAX_LENGTH}
          error={duplicate}
          helperText={duplicate ? t('secret.duplicate_name') : undefined}
          onChange={(value) => setForm({ ...form, name: value })}
        />

        {/*
         * Reading, the mask is the value: there is no stored text to show. The
         * sentence sits under it because this is where someone looks for the key
         * and does not find it — not in a banner over the list, where an
         * always-true message is skipped along with the band it sits in.
         */}
        {readOnly ? (
          <DetailField label={t('secret.value')}>
            <Stack spacing={0.25}>
              <span>{VALUE_MASK}</span>
              <Typography variant="caption" color="text.secondary">
                {t('secret.never_read')}
              </Typography>
            </Stack>
          </DetailField>
        ) : (
          <ScalarField
            label={t('secret.value')}
            value={form.value}
            readOnly={false}
            type="password"
            placeholder={secret === null ? undefined : VALUE_MASK}
            maxLength={VALUE_MAX_LENGTH}
            error={missingValue}
            helperText={secret === null ? undefined : t('secret.value_keep')}
            onChange={(value) => setForm({ ...form, value })}
          />
        )}

        <ScalarField
          label={t('secret.description')}
          value={form.description}
          readOnly={readOnly}
          maxLength={DESCRIPTION_MAX_LENGTH}
          onChange={(value) => setForm({ ...form, description: value })}
        />

        {/*
         * Secrets of one provider sharing a group are one credential: the client
         * sends whichever member is not spent. The spent state is read-only - it
         * is the provider's verdict with a clock on it, not something to edit.
         */}
        <ScalarField
          label={t('secret.rotation_group')}
          value={form.rotationGroup}
          readOnly={readOnly}
          maxLength={NAME_MAX_LENGTH}
          helperText={readOnly ? undefined : t('secret.rotation_group_hint')}
          onChange={(value) => setForm({ ...form, rotationGroup: value })}
        />

        {secret !== null && secret.rotation_group !== null && (
          <DetailField label={t('secret.exhausted_until')}>
            {secret.exhausted_until !== null && new Date(secret.exhausted_until) > new Date() ? (
              <Label variant="soft" color="warning">
                {t('secret.spent_until', { time: formatDateTime(secret.exhausted_until) })}
              </Label>
            ) : (
              <Label variant="soft" color="success">
                {t('secret.fresh')}
              </Label>
            )}
          </DetailField>
        )}

        {readOnly ? (
          <Box>
            <DetailField label={t('form.enabled')}>
              <Label variant="soft" color={form.enabled ? 'success' : 'default'}>
                {form.enabled ? tCommon('status.enabled') : tCommon('status.disabled')}
              </Label>
            </DetailField>
          </Box>
        ) : (
          <FormControlLabel
            control={
              <Switch
                checked={form.enabled}
                onChange={(event) => setForm({ ...form, enabled: event.target.checked })}
              />
            }
            label={t('form.enabled')}
          />
        )}
      </Stack>
    </Stack>
  )
}

/**
 * The form the panel starts from. `value` is always empty: there is nothing to
 * prefill it with, and a mask typed into the box would be saved as the key.
 */
function initialForm(secret: IntegrationSecret | null) {
  return {
    name: secret?.name ?? '',
    value: '',
    description: secret?.description ?? '',
    enabled: secret?.enabled ?? true,
    rotationGroup: secret?.rotation_group ?? '',
  }
}
