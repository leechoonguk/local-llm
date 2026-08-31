/**
 * Batch create/edit dialog — the form-dialog template with two fields.
 *
 * `description` is nullable on the wire, so an empty input is sent as `null`
 * rather than `""`: the column means "no description", and two spellings of
 * absent is how a filter on it starts missing rows.
 */

import { useEffect, useMemo } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { yupResolver } from '@hookform/resolvers/yup'
import * as yup from 'yup'
import { Button, Dialog, DialogActions, DialogContent, Stack } from '@mui/material'
import FormProvider from '@/components/hook-form/FormProvider'
import FormDialogHeader from '@/components/dialog/FormDialogHeader'
import RHFTextField from '@/components/hook-form/RHFTextField'
import { useCreateBatch, useUpdateBatch } from '@/lib/api/hooks/useBatch'
import { useToast } from '@/hooks/useToast'
import { applyServerError } from '@/lib/api/formErrors'
import type { Batch } from '@/types/batch'

/** Lengths mirror `BatchBase` on the server. */
const NAME_MAX_LENGTH = 120

const DESCRIPTION_MAX_LENGTH = 512

interface BatchFormValues {
  name: string
  description: string
}

const EMPTY_VALUES: BatchFormValues = { name: '', description: '' }

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
        : { name: batch.name, description: batch.description ?? '' },
    )
  }, [open, batch, methods])

  const onSubmit = async (values: BatchFormValues) => {
    const payload = {
      name: values.name,
      description: values.description === '' ? null : values.description,
    }
    try {
      if (batch === null) {
        await createMutation.mutateAsync(payload)
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
        fieldByCode: { conflict: 'name' },
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
            <RHFTextField name="name" label={t('form.name')} />
            <RHFTextField name="description" label={t('form.description')} multiline minRows={3} />
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
