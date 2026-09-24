/**
 * The mechanism a row editor needs, once, for every screen that edits in place.
 *
 * Two screens carried it and 24 of their 26 row-edit lines were byte-identical:
 * the modes map, the three commands, the deferred focus move, and the
 * `reported` flag that stops a refused save being explained twice. None of that
 * is a decision a screen makes — the decisions are `problemOf` and `refusal`,
 * which stay in the screen because they are what the domain refuses.
 *
 * `apiRef` is taken rather than created here: the screen hands the same ref to
 * `ServerDataGrid`, so the pending values this hook reads are the ones the grid
 * is showing (rule://frontend-screens, Refusing A Save).
 */

import { useCallback, useMemo, useState } from 'react'
import type { RefObject } from 'react'
import { GridRowModes } from '@mui/x-data-grid'
import type { GridApiCommunity } from '@mui/x-data-grid/internals'
import type { GridRowId, GridRowModesModel, GridValidRowModel } from '@mui/x-data-grid'
import { useToast } from '@/hooks/useToast'

/** Why a row cannot be saved: the offending cell, and the sentence to show. */
export interface RowRefusal<F extends string> {
  field: F
  sentence: string
}

interface RowEditorOptions<R extends GridValidRowModel, F extends string> {
  apiRef: RefObject<GridApiCommunity | null>
  /** The screen's own judgement of a pending row — `null` when it may be saved. */
  refusal: (row: R) => RowRefusal<F> | null
  /**
   * What the screen keeps beyond the row's mode, at the three moments it turns.
   *
   * The user list needs all three: a refused row joins the set that is allowed
   * to look wrong, a committed one leaves it, and a cancelled draft is dropped
   * rather than reverted to a version no endpoint ever stored. They are
   * optional because a screen editing saved rows only needs the modes.
   */
  onRefused?: (id: GridRowId) => void
  onCommitted?: (id: GridRowId) => void
  onCancelled?: (id: GridRowId) => void
}

/** Whether a thrown refusal already told the reader what was wrong. */
function wasReported(error: unknown): boolean {
  return error !== null && typeof error === 'object' && 'reported' in error && error.reported === true
}

export function useRowEditor<R extends GridValidRowModel, F extends string>({
  apiRef,
  refusal,
  onRefused,
  onCommitted,
  onCancelled,
}: RowEditorOptions<R, F>) {
  const toast = useToast()
  const [rowModes, setRowModes] = useState<GridRowModesModel>({})

  const startEdit = useCallback(
    (id: GridRowId) => setRowModes((previous) => ({ ...previous, [id]: { mode: GridRowModes.Edit } })),
    [],
  )

  const cancelEdit = useCallback(
    (id: GridRowId) => {
      onCancelled?.(id)
      setRowModes((previous) => ({
        ...previous,
        [id]: { mode: GridRowModes.View, ignoreModifications: true },
      }))
    },
    [onCancelled],
  )

  /**
   * Refusing a save says which cell refused, and puts the caret in it.
   *
   * The grid's own answer to an invalid row is to stay open, silently, so the
   * save button reads as broken. The focus move is deferred because the button
   * that was clicked takes focus back on its own mouse event.
   */
  const reportRefusal = useCallback(
    (id: GridRowId, problem: RowRefusal<F>) => {
      onRefused?.(id)
      toast.error(problem.sentence)
      queueMicrotask(() => {
        apiRef.current?.setCellFocus(id, problem.field)
        apiRef.current?.getCellElement(id, problem.field)?.querySelector('input')?.focus()
      })
    },
    [apiRef, onRefused, toast],
  )

  const commitEdit = useCallback(
    (id: GridRowId) => {
      // The grid answers in its own row type; the screen's row is what it was given.
      const row = apiRef.current?.getRowWithUpdatedValues(id, '') as R | undefined
      const problem = row === undefined ? null : refusal(row)
      if (problem !== null) {
        reportRefusal(id, problem)
        return
      }
      onCommitted?.(id)
      setRowModes((previous) => ({ ...previous, [id]: { mode: GridRowModes.View } }))
    },
    [apiRef, onCommitted, refusal, reportRefusal],
  )

  /**
   * The same judgement around the grid's own commit, because Enter never passes
   * the save button: a rule enforced on the click alone lets the keyboard
   * through into a 422 the server has to explain. The throw is what keeps the
   * row open, and `reported` is what stops the error handler saying a second,
   * vaguer thing about a failure already named.
   */
  const guardRowUpdate = useCallback(
    (save: (updated: R, original: R) => Promise<R> | R) => async (updated: R, original: R) => {
      const problem = refusal(updated)
      if (problem !== null) {
        // A grid row is keyed by its id, which this app spells as a uuid string.
        const id: GridRowId = updated.id
        reportRefusal(id, problem)
        throw Object.assign(new Error(problem.sentence), { reported: true })
      }
      return await save(updated, original)
    },
    [refusal, reportRefusal],
  )

  /** The sentence a failed save shows, unless the refusal already named one. */
  const rowUpdateError = useCallback(
    (error: unknown, fallback: (error: unknown) => string) => {
      if (wasReported(error)) return
      toast.error(fallback(error))
    },
    [toast],
  )

  const isEditing = useCallback(
    (id: GridRowId) => rowModes[id]?.mode === GridRowModes.Edit,
    [rowModes],
  )

  return useMemo(
    () => ({ rowModes, setRowModes, startEdit, cancelEdit, commitEdit, isEditing, guardRowUpdate, rowUpdateError }),
    [rowModes, startEdit, cancelEdit, commitEdit, isEditing, guardRowUpdate, rowUpdateError],
  )
}
