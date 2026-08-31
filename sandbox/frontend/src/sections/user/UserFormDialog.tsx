/**
 * The form-dialog template — every create/edit dialog in the app is this shape.
 *
 * One dialog serves both modes, because "create" and "edit" differ only in the
 * default values and the mutation. The schema is the single source of
 * validation: the submit button never re-checks a field by hand, so a rule can
 * only be enforced in one place.
 *
 * `password` is required on create and optional on edit — the backend treats an
 * omitted password as "keep the current one" (`UserUpdateRequest`).
 */

import { useEffect, useMemo } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { yupResolver } from '@hookform/resolvers/yup'
import * as yup from 'yup'
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  Stack,
} from '@mui/material'
import FormProvider from '@/components/hook-form/FormProvider'
import FormDialogHeader from '@/components/dialog/FormDialogHeader'
import RHFTextField from '@/components/hook-form/RHFTextField'
import { useToast } from '@/hooks/useToast'
import { applyServerError } from '@/lib/api/formErrors'
import { useCreateUser, useUpdateUser } from '@/lib/api/hooks/useUser'
import type { User } from '@/types/user'

/** Lengths mirror `UserBase` / `UserCreateRequest` on the server. */
const USERNAME_MAX_LENGTH = 50

const EMAIL_MAX_LENGTH = 255

const PASSWORD_MIN_LENGTH = 8

const PASSWORD_MAX_LENGTH = 128

interface UserFormValues {
  username: string
  email: string
  password: string
}

const EMPTY_VALUES: UserFormValues = { username: '', email: '', password: '' }

interface UserFormDialogProps {
  open: boolean
  onClose: () => void
  user: User | null
}

export default function UserFormDialog({ open, onClose, user }: UserFormDialogProps) {
  const { t } = useTranslation('user')
  const { t: tCommon } = useTranslation('common')
  const toast = useToast()

  const createMutation = useCreateUser()
  const updateMutation = useUpdateUser()
  const isEdit = user !== null

  const schema = useMemo(
    () =>
      yup.object({
        username: yup
          .string()
          .required(tCommon('validation.required'))
          .max(USERNAME_MAX_LENGTH, tCommon('validation.max_length', { count: USERNAME_MAX_LENGTH })),
        email: yup
          .string()
          .required(tCommon('validation.required'))
          .email(tCommon('validation.email'))
          .max(EMAIL_MAX_LENGTH, tCommon('validation.max_length', { count: EMAIL_MAX_LENGTH })),
        password: isEdit
          ? yup
              .string()
              .transform((value: string) => value.trim())
              .test(
                'optional-min-length',
                tCommon('validation.min_length', { count: PASSWORD_MIN_LENGTH }),
                (value) => value === undefined || value === '' || value.length >= PASSWORD_MIN_LENGTH,
              )
              .max(PASSWORD_MAX_LENGTH, tCommon('validation.max_length', { count: PASSWORD_MAX_LENGTH }))
              .defined()
          : yup
              .string()
              .required(tCommon('validation.required'))
              .min(
                PASSWORD_MIN_LENGTH,
                tCommon('validation.min_length', { count: PASSWORD_MIN_LENGTH }),
              )
              .max(
                PASSWORD_MAX_LENGTH,
                tCommon('validation.max_length', { count: PASSWORD_MAX_LENGTH }),
              ),
      }),
    [isEdit, tCommon],
  )

  const methods = useForm<UserFormValues>({
    resolver: yupResolver(schema),
    defaultValues: EMPTY_VALUES,
  })

  // The dialog stays mounted between rows, so the values are reset on open
  // rather than on mount — otherwise the second row edited shows the first.
  useEffect(() => {
    if (!open) return
    methods.reset(
      user === null ? EMPTY_VALUES : { username: user.username, email: user.email, password: '' },
    )
  }, [open, user, methods])

  const onSubmit = async (values: UserFormValues) => {
    try {
      if (user === null) {
        await createMutation.mutateAsync(values)
        toast.success(tCommon('messages.created'))
      } else {
        await updateMutation.mutateAsync({
          id: user.id,
          data: {
            username: values.username,
            email: values.email,
            password: values.password === '' ? undefined : values.password,
          },
        })
        toast.success(tCommon('messages.updated'))
      }
      onClose()
    } catch (error) {
      // The server answers one `conflict` for a taken username and a taken
      // email, so it cannot name the field: the sentence goes to the toast.
      applyServerError(error, {
        t: tCommon,
        setError: methods.setError,
        toastError: toast.error,
      })
    }
  }

  const pending = createMutation.isPending || updateMutation.isPending

  return (
    <Dialog open={open} onClose={onClose}>
      <FormProvider methods={methods} onSubmit={methods.handleSubmit(onSubmit)}>
        <FormDialogHeader
          name={isEdit ? 'edit' : 'people'}
          title={isEdit ? t('edit_title') : t('create_title')}
          caption={user?.email}
          onClose={onClose}
        />

        <DialogContent sx={{ p: 2 }}>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <RHFTextField name="username" label={t('form.username')} />
            <RHFTextField name="email" label={t('form.email')} type="email" />
            <RHFTextField
              name="password"
              label={t('form.password')}
              type="password"
              helperText={isEdit ? t('form.password_keep') : undefined}
            />
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
