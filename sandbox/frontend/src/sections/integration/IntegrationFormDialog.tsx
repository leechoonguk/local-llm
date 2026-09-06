/**
 * Provider create/edit dialog.
 *
 * `code` is the provider's identity: the backend resolves an operation by it
 * (`execute_operation(provider.code, ...)`) and `IntegrationUpdateRequest` has
 * no `code` field at all. So the input is disabled in edit mode rather than
 * sent and silently ignored.
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
import { useCreateIntegration } from '@/lib/api/hooks/useIntegration'
import { useToast } from '@/hooks/useToast'
import { applyServerError } from '@/lib/api/formErrors'

/**
 * Lengths mirror `IntegrationCreateRequest`; the two patterns mirror
 * `IntegrationService._validate_provider`, which is where this API's real
 * shape rules live — not in the Pydantic schema. Reading only the schema is how
 * this form ended up with `^[a-z][a-z0-9_]*$`: underscores the server refuses
 * and no hyphen, so it could not create `mfds-food-safety-korea`, the provider
 * the app itself seeds.
 */
const CODE_MAX_LENGTH = 64

export const DISPLAY_NAME_MAX_LENGTH = 120

export const BASE_URL_MAX_LENGTH = 2048

/** `CODE_PATTERN` in `app/services/integration.py`. */
const CODE_PATTERN = /^[a-z0-9-]+$/

/**
 * `_validate_base_url`: an HTTPS origin and nothing else — no path beyond `/`,
 * no query, no fragment, no credentials.
 */
export const HTTPS_ORIGIN_PATTERN = /^https:\/\/[^/?#@\s]+\/?$/

interface IntegrationFormValues {
  code: string
  display_name: string
  base_url: string
  enabled: boolean
}

const EMPTY_VALUES: IntegrationFormValues = {
  code: '',
  display_name: '',
  base_url: '',
  enabled: true,
}

interface IntegrationFormDialogProps {
  open: boolean
  onClose: () => void
}

export default function IntegrationFormDialog({
  open,
  onClose,
}: IntegrationFormDialogProps) {
  const { t } = useTranslation('integration')
  const { t: tCommon } = useTranslation('common')
  const toast = useToast()

  const createMutation = useCreateIntegration()

  const schema = useMemo(
    () =>
      yup.object({
        code: yup
          .string()
          .required(tCommon('validation.required'))
          .max(CODE_MAX_LENGTH, tCommon('validation.max_length', { count: CODE_MAX_LENGTH }))
          .matches(CODE_PATTERN, tCommon('errors.provider_code_invalid')),
        display_name: yup
          .string()
          .required(tCommon('validation.required'))
          .max(
            DISPLAY_NAME_MAX_LENGTH,
            tCommon('validation.max_length', { count: DISPLAY_NAME_MAX_LENGTH }),
          ),
        base_url: yup
          .string()
          .required(tCommon('validation.required'))
          .max(BASE_URL_MAX_LENGTH, tCommon('validation.max_length', { count: BASE_URL_MAX_LENGTH }))
          .matches(HTTPS_ORIGIN_PATTERN, tCommon('errors.provider_base_url_invalid')),
        enabled: yup.boolean().defined(),
      }),
    [tCommon],
  )

  const methods = useForm<IntegrationFormValues>({
    resolver: yupResolver(schema),
    defaultValues: EMPTY_VALUES,
  })

  useEffect(() => {
    if (!open) return
    methods.reset(EMPTY_VALUES)
  }, [open, methods])

  const onSubmit = async (values: IntegrationFormValues) => {
    try {
      await createMutation.mutateAsync(values)
      toast.success(tCommon('messages.created'))
      onClose()
    } catch (error) {
      // A taken code is a fact about the `code` input, so it belongs on it.
      applyServerError(error, {
        t: tCommon,
        setError: methods.setError,
        toastError: toast.error,
        fieldByCode: {
          provider_code_taken: 'code',
          provider_code_invalid: 'code',
          provider_base_url_invalid: 'base_url',
        },
      })
    }
  }

  const pending = createMutation.isPending

  return (
    <Dialog open={open} onClose={onClose}>
      <FormProvider methods={methods} onSubmit={methods.handleSubmit(onSubmit)}>
        <FormDialogHeader name="link" title={t('create_title')} onClose={onClose} />

        <DialogContent sx={{ p: 2 }}>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <RHFTextField name="code" label={t('form.code')} />
            <RHFTextField name="display_name" label={t('form.display_name')} />
            <RHFTextField name="base_url" label={t('form.base_url')} />
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
