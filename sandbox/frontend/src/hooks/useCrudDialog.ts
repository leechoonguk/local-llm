/**
 * One state machine for a screen's create/edit/delete dialogs.
 *
 * Four booleans and a selected row is the shape every list screen kept
 * re-inventing, and the versions drifted: some closed by clearing the row,
 * others by flipping a flag, so a closing dialog flashed empty fields. A single
 * `mode` cannot be in two states at once.
 */

import { useCallback, useMemo, useState } from 'react'

export type CrudMode = 'create' | 'edit' | 'delete' | 'view' | null

export function useCrudDialog<T>() {
  const [mode, setMode] = useState<CrudMode>(null)
  const [selected, setSelected] = useState<T | null>(null)

  const openCreate = useCallback(() => {
    setSelected(null)
    setMode('create')
  }, [])

  const openEdit = useCallback((item: T) => {
    setSelected(item)
    setMode('edit')
  }, [])

  const openDelete = useCallback((item: T) => {
    setSelected(item)
    setMode('delete')
  }, [])

  const openView = useCallback((item: T) => {
    setSelected(item)
    setMode('view')
  }, [])

  // The row survives the close so the dialog can animate out with its content.
  const close = useCallback(() => setMode(null), [])

  return useMemo(
    () => ({
      mode,
      selected,
      isCreateOpen: mode === 'create',
      isEditOpen: mode === 'edit',
      isDeleteOpen: mode === 'delete',
      isViewOpen: mode === 'view',
      openCreate,
      openEdit,
      openDelete,
      openView,
      close,
    }),
    [mode, selected, openCreate, openEdit, openDelete, openView, close],
  )
}
