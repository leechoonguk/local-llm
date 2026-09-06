/**
 * Destructive-action confirmation — the question every delete goes through.
 *
 * The head is the app's dialog head (`FormDialogHeader`) in the error tone, so
 * the question that destroys a row is recognisably the same surface as the form
 * that edits it: one icon size, one title weight, one close button, one dashed
 * rule. Without it the dialog read as a stray paragraph with buttons under it.
 *
 * **The body is one sentence.** It was two — the row, then "이 작업은 되돌릴 수
 * 없습니다" as a caption — and the split implied two facts of different weight
 * where there is one: deleting *this row* is what cannot be undone. A caption is
 * for something the reader may skip, and the cost of a delete is not that. So
 * the domain's own sentence carries both (`messages.delete_confirm`), and the
 * title above it names the verb once instead of the body repeating it.
 *
 * `xs` and `fullWidth`, so the question is the same width wherever it is asked;
 * shrink-wrapped, a long name made a wide dialog and a short one a narrow one.
 * The confirm button carries the delete icon and the error colour it has in the
 * record panels, and stays disabled while the request is in flight so a double
 * click cannot send it twice.
 */

import { Button, Dialog, DialogActions, DialogContent, Divider, Typography } from '@mui/material'
import type { ReactNode } from 'react'
import FormDialogHeader from '@/components/dialog/FormDialogHeader'
import Iconify from '@/components/iconify/Iconify'

interface ConfirmDialogProps {
  open: boolean
  title: string
  /** One sentence: which row disappears, and what that costs. */
  content: ReactNode
  confirmLabel: string
  cancelLabel: string
  pending: boolean
  onConfirm: () => void
  onClose: () => void
}

export default function ConfirmDialog({
  open,
  title,
  content,
  confirmLabel,
  cancelLabel,
  pending,
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <FormDialogHeader name="delete" tone="error" title={title} onClose={onClose} />

      <DialogContent sx={{ p: 2 }}>
        <Typography variant="body2">{content}</Typography>
      </DialogContent>

      <Divider sx={{ borderStyle: 'dashed' }} />

      <DialogActions sx={{ py: 1.5, px: 2 }}>
        <Button variant="outlined" color="inherit" size="small" onClick={onClose}>
          {cancelLabel}
        </Button>
        <Button
          variant="contained"
          color="error"
          size="small"
          startIcon={<Iconify name="delete" />}
          onClick={onConfirm}
          disabled={pending}
        >
          {confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
