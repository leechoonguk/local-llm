/**
 * Delete confirmation for one operation.
 *
 * The count is the cost: the server stores the operations array, so removing a
 * member removes its wire fields with it. The frame is `RecordDeletePanel`, shared
 * with the credential panel — one pinned strip, one cancel, one delete.
 */

import { useState } from 'react'
import { Alert, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import Label from '@/components/label/Label'
import RecordDeletePanel from '@/components/detail/RecordDeletePanel'
import { applyServerError } from '@/lib/api/formErrors'
import { useUpdateIntegration } from '@/lib/api/hooks/useIntegration'
import { useToast } from '@/hooks/useToast'
import { toOperationRequest } from '@/sections/integration/IntegrationOperationPanel'
import type { Integration, IntegrationOperation } from '@/types/integration'

interface IntegrationOperationDeletePanelProps {
  provider: Integration
  operation: IntegrationOperation
  onBack: () => void
}

export default function IntegrationOperationDeletePanel({
  provider,
  operation,
  onBack,
}: IntegrationOperationDeletePanelProps) {
  const { t } = useTranslation('integration')
  const { t: tCommon } = useTranslation('common')
  const toast = useToast()
  const update = useUpdateIntegration()
  const [failure, setFailure] = useState<string | null>(null)

  const remove = async () => {
    setFailure(null)
    try {
      await update.mutateAsync({
        id: provider.id,
        data: {
          operations: provider.operations
            .filter((existing) => existing.id !== operation.id)
            .map(toOperationRequest),
        },
      })
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
      title={t('operation.delete_title')}
      summary={
        <>
          <Label color="info">{operation.method}</Label>
          <Typography variant="subtitle2">{operation.code}</Typography>
          <Typography variant="body2" color="text.secondary" noWrap>
            {operation.path_template}
          </Typography>
        </>
      }
      warning={
        <Alert severity="warning">
          {t('operation.delete_warning', { count: operation.fields.length })}
        </Alert>
      }
      pending={update.isPending}
      failure={failure}
      onBack={onBack}
      onConfirm={() => void remove()}
    />
  )
}
