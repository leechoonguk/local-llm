/**
 * Destructive-action confirmation, ported from the reference application.
 *
 * The chrome is the design: `xs` width, tight title padding, a dashed divider
 * above and below the body, and an **outlined** cancel beside the destructive
 * action — both `small`. A dialog that asks "are you sure" should read as a
 * question, not as a page.
 *
 * Delete is the one action with no undo in this API, so it always goes through
 * here: the row it will destroy is named in the body, and the button stays
 * disabled while the mutation is in flight so a double click cannot send the
 * request twice.
 */

import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
} from '@mui/material'
import type { ReactNode } from 'react'

interface ConfirmDialogProps {
  open: boolean
  title: string
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
    <Dialog open={open} onClose={onClose} maxWidth="xs">
      <DialogTitle sx={{ py: 1.5, px: 2 }}>{title}</DialogTitle>

      <Divider sx={{ borderStyle: 'dashed' }} />

      <DialogContent sx={{ p: 2, typography: 'body2' }}>{content}</DialogContent>

      <Divider sx={{ borderStyle: 'dashed' }} />

      <DialogActions sx={{ py: 1.5, px: 2 }}>
        <Button variant="outlined" color="inherit" size="small" onClick={onClose}>
          {cancelLabel}
        </Button>
        <Button
          variant="contained"
          color="error"
          size="small"
          onClick={onConfirm}
          disabled={pending}
        >
          {confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
