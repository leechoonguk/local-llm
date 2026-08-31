/**
 * The head of a form dialog, ported from the reference application.
 *
 * Tight padding, a primary-tinted icon, a bold `subtitle1` title, the record's
 * identity as a caption under it, a close button, and a dashed divider. The
 * reference application repeats this block in every dialog; here it is one
 * component, so "what a form dialog looks like" is a single definition.
 *
 * The caption is what tells the user *which* row they are editing — a dialog
 * titled only "Edit user" is the same dialog for every row.
 */

import { DialogTitle, Divider, IconButton, Stack, Typography } from '@mui/material'
import Iconify from '@/components/iconify/Iconify'
import type { ActionIcon } from '@/components/iconify/icons'

const ICON_SIZE = 20

const CAPTION_INDENT = 3.5

interface FormDialogHeaderProps {
  name: ActionIcon
  title: string
  /** The row being edited, shown under the title. Absent when creating. */
  caption?: string
  onClose: () => void
}

export default function FormDialogHeader({
  name,
  title,
  caption,
  onClose,
}: FormDialogHeaderProps) {
  return (
    <>
      <DialogTitle sx={{ py: 1.5, px: 2 }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Stack>
            <Stack direction="row" alignItems="center" spacing={1}>
              <Iconify name={name} width={ICON_SIZE} sx={{ color: 'primary.main' }} />
              <Typography variant="subtitle1" fontWeight="bold">
                {title}
              </Typography>
            </Stack>

            {caption !== undefined && (
              <Typography variant="caption" color="text.secondary" sx={{ pl: CAPTION_INDENT }}>
                {caption}
              </Typography>
            )}
          </Stack>

          <IconButton onClick={onClose} size="small">
            <Iconify name="close" />
          </IconButton>
        </Stack>
      </DialogTitle>

      <Divider sx={{ borderStyle: 'dashed' }} />
    </>
  )
}
