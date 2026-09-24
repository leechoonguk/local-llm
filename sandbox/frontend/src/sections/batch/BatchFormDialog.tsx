/**
 * Batch create dialog — the form-dialog template for a new job schedule.
 *
 * It creates and never edits. A schedule's editable values are `cron` and
 * `enabled`, and both are columns the row types into
 * (rule://frontend-screens, Editing In Place): a dialog for them would be a
 * second surface asking for what the row already shows. The create stays here
 * because `code` is chosen once and never again — the server refuses to repoint
 * an existing schedule at another job, so the field exists only while creating.
 *
 * The length limits are exported: the row editor judges the same value, and a
 * second copy of 120 is how a cell starts accepting what the dialog refuses.
 */

import { useEffect, useMemo } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { yupResolver } from '@hookform/resolvers/yup'
import * as yup from 'yup'
import { Button, Dialog, DialogActions, DialogContent, Stack } from '@mui/material'
import FormProvider from '@/components/hook-form/FormProvider'
import FormDialogHeader from '@/components/dialog/FormDialogHeader'
import RHFSwitch from '@/components/hook-form/RHFSwitch'
import RHFTextField from '@/components/hook-form/RHFTextField'
import { useCreateBatch } from '@/lib/api/hooks/useBatch'
import { useToast } from '@/hooks/useToast'
import { applyServerError } from '@/lib/api/formErrors'

/** Lengths mirror `BatchBase` on the server. */
export const CODE_MAX_LENGTH = 64

export const CRON_MAX_LENGTH = 120

/**
 * Five whitespace-separated fields — the shape `validated_cron` parses.
 *
 * A shape, not a grammar: the server owns which values a field may hold and
 * answers 422 for the rest. What this catches is the mistake a cell invites —
 * a half-typed expression committed by Enter — before it becomes a round trip.
 */
export const CRON_FIELD_PATTERN = /^\S+(?:\s+\S+){4}$/

interface BatchFormValues {
  code: string
  cron: string
  enabled: boolean
}

const EMPTY_VALUES: BatchFormValues = {
  code: '',
  cron: '0 3 * * *',
  enabled: true,
}

interface BatchFormDialogProps {
  open: boolean
  onClose: () => void
}

export default function BatchFormDialog({ open, onClose }: BatchFormDialogProps) {
  const { t } = useTranslation('batch')
  const { t: tCommon } = useTranslation('common')
  const toast = useToast()

  const createMutation = useCreateBatch()

  const schema = useMemo(
    () =>
      yup.object({
        code: yup
          .string()
          .required(tCommon('validation.required'))
          .max(CODE_MAX_LENGTH, tCommon('validation.max_length', { count: CODE_MAX_LENGTH })),
        cron: yup
          .string()
          .required(tCommon('validation.required'))
          .max(CRON_MAX_LENGTH, tCommon('validation.max_length', { count: CRON_MAX_LENGTH }))
          .matches(CRON_FIELD_PATTERN, t('validation.cron_invalid')),
        enabled: yup.boolean().defined(),
      }),
    [t, tCommon],
  )

  const methods = useForm<BatchFormValues>({
    resolver: yupResolver(schema),
    defaultValues: EMPTY_VALUES,
  })

  useEffect(() => {
    if (!open) return
    methods.reset(EMPTY_VALUES)
  }, [open, methods])

  const onSubmit = async (values: BatchFormValues) => {
    const payload = {
      code: values.code,
      cron: values.cron,
      enabled: values.enabled,
    }
    try {
      await createMutation.mutateAsync(payload)
      toast.success(tCommon('messages.created'))
      onClose()
    } catch (error) {
      applyServerError(error, {
        t: tCommon,
        setError: methods.setError,
        toastError: toast.error,
        // No field mapping: a batch conflict is `already running`, `unregistered
        // job` or `no scheduler`, none of which is about a value in this form.
        // `conflict: 'code'` would put those sentences on the code input, which
        // is not what any of them is about.
      })
    }
  }

  return (
    <Dialog open={open} onClose={onClose}>
      <FormProvider methods={methods} onSubmit={methods.handleSubmit(onSubmit)}>
        <FormDialogHeader name="layers" title={t('create_title')} onClose={onClose} />

        <DialogContent sx={{ p: 2 }}>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <RHFTextField name="code" label={t('form.code')} helperText={t('form.code_helper')} />
            <RHFTextField name="cron" label={t('form.cron')} helperText={t('form.cron_helper')} />
            <RHFSwitch name="enabled" label={t('form.enabled')} />
          </Stack>
        </DialogContent>

        <DialogActions sx={{ py: 1.5, px: 2 }}>
          <Button color="inherit" onClick={onClose}>
            {tCommon('actions.cancel')}
          </Button>
          <Button type="submit" variant="contained" disabled={createMutation.isPending}>
            {tCommon('actions.save')}
          </Button>
        </DialogActions>
      </FormProvider>
    </Dialog>
  )
}
