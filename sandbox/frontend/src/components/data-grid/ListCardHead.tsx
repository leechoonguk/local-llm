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
 * **A ledger has no add.** The `food_*` collections are filled by a nightly sync
 * and read here; a row a user typed would be overwritten on the next pass, and
 * the backend has no verb to receive it. So `add` is one optional object — the
 * label and the handler travel together, because an add button with a handler
 * and no label, or the reverse, is half a control.
 */

import { CircularProgress, Divider, IconButton, Stack, Tab, Tabs, Tooltip } from '@mui/material'
import type { ReactNode } from 'react'
import Iconify from '@/components/iconify/Iconify'
import Label from '@/components/label/Label'

const SPINNER_SIZE = 20

interface ListCardHeadProps {
  /** The tab label — the collection's name. */
  title: string
  /** The total under the current filters, shown as the tab's count badge. */
  count: number
  /** One box per filterable column, plus the control that clears them. */
  filters: ReactNode
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
          Wraps: six boxes at 1400px ran 130px past the card's edge and the
          last select sat off-screen - measured, its centre was at x=1530. A
          filter nobody can reach is a filter that does not exist.
        */}
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          alignItems={{ sm: 'center' }}
          spacing={2}
          useFlexGap
          flexWrap="wrap"
        >
          {filters}
        </Stack>

        <Stack direction="row" alignItems="center" spacing={0.5}>
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
