/**
 * The head of a list card: what the collection is, what narrows it, what acts on it.
 *
 * Two rows. First a tab strip whose label carries the total as a `Label` — the
 * total under the filters, so the badge and the footer never disagree about how
 * much data is behind the screen. Then one row: the screen's filter fields on
 * the left, and on the right the two controls every list has — add a row, and
 * re-read the page.
 *
 * It replaced `ListToolbar`, which put the add button alone on its own row above
 * the filters. The eye crossed the card twice to read one line, and the row that
 * held a single button also held a density control that changed how the rows
 * looked and nothing about what they are.
 *
 * **The fields are the screen's, the frame is not.** Which columns a list
 * filters is domain knowledge — `username`/`email` here, `code`/`display_name`
 * there — so they arrive as a node; a generic search box in this component
 * would have to guess what it searches. What the frame owns is the geometry: the
 * filters left, the verbs right, always the same two, always in that order.
 *
 * Add is an icon, not a labelled button: it adds a row *to this table*, and the
 * table's own operations are icons on the table's own row.
 *
 * **A derived table has no add.** The `food_*` collections are rebuilt off the
 * ledgers by a nightly job and read here; a row a user typed would be gone by
 * morning, and the backend has no verb to receive it. So `add` is one optional object — the
 * label and the handler travel together, because an add button with a handler
 * and no label, or the reverse, is half a control.
 */

import { Box, CircularProgress, Divider, IconButton, Stack, Tab, Tabs, Tooltip } from '@mui/material'
import type { ReactNode } from 'react'
import Iconify from '@/components/iconify/Iconify'
import Label from '@/components/label/Label'

/** The narrowest a filter box may be: a 16-digit registry number or a 7-syllable industry name without clipping. */
const FILTER_MIN = 200

const SPINNER_SIZE = 20

interface ListCardHeadProps {
  /** The tab label — the collection's name. */
  title: string
  /** The total under the current filters, shown as the tab's count badge. */
  count: number
  /** One box per filterable column. */
  filters: ReactNode
  /**
   * The control that clears every box, beside the refresh: it acts on the
   * whole head, not on one box, and inside the grid it was the seventh cell -
   * alone on a third row whenever the boxes filled their rows exactly
   * (measured at 900px, 6 boxes in 2 rows of 3).
   */
  reset: { label: string; onReset: () => void; disabled: boolean }
  /**
   * The control that adds a row, or nothing on a read-only ledger.
   * `disabled` is `true` while a row is being added, so a second draft cannot start.
   */
  add?: { label: string; onAdd: () => void; disabled?: boolean }
  refreshLabel: string
  onRefresh: () => void
  refreshing: boolean
}

export default function ListCardHead({
  title,
  count,
  filters,
  reset,
  add,
  refreshLabel,
  onRefresh,
  refreshing,
}: ListCardHeadProps) {
  return (
    <>
      <Tabs value="all" sx={{ px: 2.5, bgcolor: 'background.neutral' }}>
        <Tab
          value="all"
          label={
            <Stack direction="row" alignItems="center" spacing={1}>
              <span>{title}</span>
              <Label variant="soft" color="default">
                {count}
              </Label>
            </Stack>
          }
        />
      </Tabs>

      <Divider />

      <Stack
        direction={{ xs: 'column', md: 'row' }}
        alignItems={{ md: 'center' }}
        justifyContent="space-between"
        spacing={2}
        sx={{ px: 2.5, py: 2 }}
      >
        {/*
          A grid of equal cells, as many per row as fit at FILTER_MIN each, and
          the cells stretch to fill the row. Fixed widths wrapped: six boxes at
          1400px ran 130px past the card's edge (measured, the last select's
          centre at x=1530), and at 900px they folded into 3+3 with a ragged
          right edge and the reset stranded beside the gap. A filter nobody can
          reach is a filter that does not exist; a row that ends short of the
          edge reads as unfinished.
        */}
        <Box
          sx={{
            flexGrow: 1,
            display: 'grid',
            gap: 2,
            alignItems: 'center',
            gridTemplateColumns: { xs: '1fr', sm: `repeat(auto-fit, minmax(${FILTER_MIN}px, 1fr))` },
          }}
        >
          {filters}
        </Box>

        <Stack
          direction="row"
          alignItems="center"
          spacing={0.5}
          // Below md the head is a column and this row would strand at the left;
          // the filters' reset already sits at the right, so this joins it there.
          sx={{ alignSelf: { xs: 'flex-end', md: 'auto' } }}
        >
          <Tooltip title={reset.label}>
            <span>
              <IconButton color="error" disabled={reset.disabled} onClick={reset.onReset}>
                <Iconify name="delete" />
              </IconButton>
            </span>
          </Tooltip>

          {add !== undefined && (
            <Tooltip title={add.label}>
              <span>
                <IconButton color="primary" onClick={add.onAdd} disabled={add.disabled === true}>
                  <Iconify name="add" />
                </IconButton>
              </span>
            </Tooltip>
          )}

          <Tooltip title={refreshLabel}>
            <span>
              <IconButton onClick={onRefresh} disabled={refreshing}>
                {refreshing ? <CircularProgress size={SPINNER_SIZE} /> : <Iconify name="refresh" />}
              </IconButton>
            </span>
          </Tooltip>
        </Stack>
      </Stack>

      <Divider />
    </>
  )
}
