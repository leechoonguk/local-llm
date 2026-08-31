/**
 * The auth template — a form whose submit changes the session, not a resource.
 *
 * Failure is shown inside the form (`setError('root')`), never as a toast: the
 * message belongs next to the fields the user has to correct. The field is
 * `username`, because that is what the OAuth2 password form sends.
 */

import { useMemo } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { yupResolver } from '@hookform/resolvers/yup'
import { toApiError } from '@/lib/api/errors'
import { serverErrorMessage } from '@/lib/api/formErrors'
import * as yup from 'yup'
import { Alert, Button, Stack, Typography } from '@mui/material'
import FormProvider from '@/components/hook-form/FormProvider'
import RHFTextField from '@/components/hook-form/RHFTextField'
import { useAuthContext } from '@/auth/useAuthContext'
import { PATHS } from '@/routes/paths'

interface LoginFormValues {
  username: string
  password: string
}

const EMPTY_VALUES: LoginFormValues = { username: '', password: '' }

export default function LoginForm() {
  const { t } = useTranslation('auth')
  const { t: tCommon } = useTranslation('common')
  const { login } = useAuthContext()
  const navigate = useNavigate()

  const schema = useMemo(
    () =>
      yup.object({
        username: yup.string().required(tCommon('validation.required')),
        password: yup.string().required(tCommon('validation.required')),
      }),
    [tCommon],
  )

  const methods = useForm<LoginFormValues>({
    resolver: yupResolver(schema),
    defaultValues: EMPTY_VALUES,
  })

  const onSubmit = async (values: LoginFormValues) => {
    try {
      await login(values.username, values.password)
      void navigate(PATHS.dashboard, { replace: true })
    } catch (error) {
      // The server distinguishes bad credentials from an unreachable service;
      // one generic sentence would throw that away.
      methods.setError('root', {
        message: serverErrorMessage(toApiError(error).code, tCommon),
      })
    }
  }

  const rootError = methods.formState.errors.root?.message

  return (
    <FormProvider methods={methods} onSubmit={methods.handleSubmit(onSubmit)}>
      <Stack spacing={3}>
        <Stack spacing={0.5}>
          <Typography variant="h4">{t('login.title')}</Typography>
          <Typography variant="body2" color="text.secondary">
            {t('login.subtitle')}
          </Typography>
        </Stack>

        {rootError !== undefined && <Alert severity="error">{rootError}</Alert>}

        <RHFTextField name="username" label={t('login.username')} autoComplete="username" />
        <RHFTextField
          name="password"
          label={t('login.password')}
          type="password"
          autoComplete="current-password"
        />

        <Button
          type="submit"
          size="large"
          variant="contained"
          disabled={methods.formState.isSubmitting}
        >
          {t('login.submit')}
        </Button>
      </Stack>
    </FormProvider>
  )
}
