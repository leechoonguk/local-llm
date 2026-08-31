/**
 * Delete confirmation for one credential.
 *
 * The cost is named before the click: the secret's FK is `ON DELETE RESTRICT`, so
 * a credential a request field still references answers 409 instead of vanishing.
 * The panel says which fields hold it, because that is the list someone has to
 * change first. The frame is `RecordDeletePanel`; only this reason is local.
 */

import { useState } from 'react'
import { Alert, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import Label from '@/components/label/Label'
import RecordDeletePanel from '@/components/detail/RecordDeletePanel'
import { applyServerError } from '@/lib/api/formErrors'
import { useDeleteSecret } from '@/lib/api/hooks/useIntegration'
import { useToast } from '@/hooks/useToast'
import type { Integration, IntegrationSecret } from '@/types/integration'

interface IntegrationSecretDeletePanelProps {
  provider: Integration
  secret: IntegrationSecret
  onBack: () => void
}

export default function IntegrationSecretDeletePanel({
  provider,
  secret,
  onBack,
}: IntegrationSecretDeletePanelProps) {
  const { t } = useTranslation('integration')
  const { t: tCommon } = useTranslation('common')
  const toast = useToast()
  const remove = useDeleteSecret(provider.id)
  const [failure, setFailure] = useState<string | null>(null)

  /** The fields that name this credential — the server refuses while any remain. */
  const references = provider.operations.flatMap((operation) =>
    operation.fields
      .filter((field) => field.secret_name === secret.name)
      .map((field) => `${operation.code} · ${field.key}`),
  )

  const confirm = async () => {
    setFailure(null)
    try {
      await remove.mutateAsync(secret.name)
      toast.success(tCommon('messages.deleted'))
      onBack()
    } catch (error) {
      applyServerError(error, {
        t: tCommon,
        setError: () => setFailure(null),
        toastError: (message: string) => setFailure(message),
      })
    }
  }

  return (
    <RecordDeletePanel
      title={t('secret.delete_title')}
      summary={
        <>
          <Label variant="soft" color={secret.enabled ? 'success' : 'default'}>
            {secret.enabled ? tCommon('status.enabled') : tCommon('status.disabled')}
          </Label>
          <Typography variant="subtitle2">{secret.name}</Typography>
          <Typography variant="body2" color="text.secondary" noWrap>
            {secret.description ?? ''}
          </Typography>
        </>
      }
      warning={
        references.length === 0 ? (
          <Alert severity="warning">{tCommon('messages.cannot_undo')}</Alert>
        ) : (
          <Alert severity="error">
            {t('secret.referenced_by', { fields: references.join(', ') })}
          </Alert>
        )
      }
      blocked={references.length > 0}
      pending={remove.isPending}
      failure={failure}
      onBack={onBack}
      onConfirm={() => void confirm()}
    />
  )
}
