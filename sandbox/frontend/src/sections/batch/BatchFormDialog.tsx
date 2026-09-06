/**
 * Batch create/edit dialog — the form-dialog template for a job schedule.
 *
 * `description` is nullable on the wire, so an empty input is sent as `null`
 * rather than `""`: the column means "no description", and two spellings of
 * absent is how a filter on it starts missing rows.
 *
 * `code` is only editable while creating. The server refuses to repoint an
 * existing schedule at another job, so an editable field here would offer a
 * change that always answers 422.
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
import { useCreateBatch, useUpdateBatch } from '@/lib/api/hooks/useBatch'
import { useToast } from '@/hooks/useToast'
import { applyServerError } from '@/lib/api/formErrors'
import type { Batch } from '@/types/batch'

/** Lengths mirror `BatchBase` on the server. */
const NAME_MAX_LENGTH = 120

const DESCRIPTION_MAX_LENGTH = 512

const CODE_MAX_LENGTH = 64

const CRON_MAX_LENGTH = 120

interface BatchFormValues {
  code: string
  name: string
  description: string
  cron: string
  enabled: boolean
}

const EMPTY_VALUES: BatchFormValues = {
  code: '',
  name: '',
  description: '',
  cron: '0 3 * * *',
  enabled: true,
}

interface BatchFormDialogProps {
  open: boolean
  onClose: () => void
  batch: Batch | null
}

export default function BatchFormDialog({ open, onClose, batch }: BatchFormDialogProps) {
  const { t } = useTranslation('batch')
  const { t: tCommon } = useTranslation('common')
  const toast = useToast()

  const createMutation = useCreateBatch()
  const updateMutation = useUpdateBatch()
  const isEdit = batch !== null

  const schema = useMemo(
    () =>
      yup.object({
        code: yup
          .string()
          .required(tCommon('validation.required'))
          .max(CODE_MAX_LENGTH, tCommon('validation.max_length', { count: CODE_MAX_LENGTH })),
        name: yup
          .string()
          .required(tCommon('validation.required'))
          .max(NAME_MAX_LENGTH, tCommon('validation.max_length', { count: NAME_MAX_LENGTH })),
        description: yup
          .string()
          .max(
            DESCRIPTION_MAX_LENGTH,
            tCommon('validation.max_length', { count: DESCRIPTION_MAX_LENGTH }),
          )
          .defined(),
        cron: yup
          .string()
          .required(tCommon('validation.required'))
          .max(CRON_MAX_LENGTH, tCommon('validation.max_length', { count: CRON_MAX_LENGTH })),
        enabled: yup.boolean().defined(),
      }),
    [tCommon],
  )

  const methods = useForm<BatchFormValues>({
    resolver: yupResolver(schema),
    defaultValues: EMPTY_VALUES,
  })

  useEffect(() => {
    if (!open) return
    methods.reset(
      batch === null
        ? EMPTY_VALUES
        : {
            code: batch.code,
            name: batch.name,
            description: batch.description ?? '',
            cron: batch.cron,
            enabled: batch.enabled,
          },
    )
  }, [open, batch, methods])

  const onSubmit = async (values: BatchFormValues) => {
    const payload = {
      name: values.name,
      description: values.description === '' ? null : values.description,
      cron: values.cron,
      enabled: values.enabled,
    }
    try {
      if (batch === null) {
        await createMutation.mutateAsync({ ...payload, code: values.code })
        toast.success(tCommon('messages.created'))
      } else {
        await updateMutation.mutateAsync({ id: batch.id, data: payload })
        toast.success(tCommon('messages.updated'))
      }
      onClose()
    } catch (error) {
      applyServerError(error, {
        t: tCommon,
        setError: methods.setError,
        toastError: toast.error,
        // No field mapping: a batch conflict is `already running`, `unregistered
        // job` or `no scheduler`, none of which is about a value in this form.
        // `conflict: 'name'` put those sentences on the name input.
      })
    }
  }

  const pending = createMutation.isPending || updateMutation.isPending

  return (
    <Dialog open={open} onClose={onClose}>
      <FormProvider methods={methods} onSubmit={methods.handleSubmit(onSubmit)}>
        <FormDialogHeader
          name={isEdit ? 'edit' : 'layers'}
          title={isEdit ? t('edit_title') : t('create_title')}
          caption={batch?.name}
          onClose={onClose}
        />

        <DialogContent sx={{ p: 2 }}>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <RHFTextField
              name="code"
              label={t('form.code')}
              disabled={isEdit}
              helperText={t('form.code_helper')}
            />
            <RHFTextField name="name" label={t('form.name')} />
            <RHFTextField name="cron" label={t('form.cron')} helperText={t('form.cron_helper')} />
            <RHFTextField name="description" label={t('form.description')} multiline minRows={3} />
            <RHFSwitch name="enabled" label={t('form.enabled')} />
          </Stack>
        </DialogContent>

        <DialogActions sx={{ py: 1.5, px: 2 }}>
          <Button color="inherit" onClick={onClose}>
            {tCommon('actions.cancel')}
          </Button>
          <Button type="submit" variant="contained" disabled={pending}>
            {tCommon('actions.save')}
          </Button>
        </DialogActions>
      </FormProvider>
    </Dialog>
  )
}
