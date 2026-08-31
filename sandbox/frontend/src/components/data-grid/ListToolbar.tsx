/**
 * The head of a list card, ported from the reference application.
 *
 * Two rows, in this order: a tab strip whose label carries the row count as a
 * `Label`, then the action row. The count belongs in the tab because that is
 * where a reader looks to know how much data is behind the screen, and the
 * actions sit on the right so the primary button is always in the same place.
 *
 * There is no search field and no sort control: no list endpoint accepts a
 * keyword or a sort parameter (`app/dependencies/query.py`), and a box that
 * filters the ten rows already on screen reports a result the collection does
 * not have.
 */

import { Button, CircularProgress, Divider, IconButton, Stack, Tab, Tabs, Tooltip } from '@mui/material'
import type { GridDensity } from '@mui/x-data-grid'
import Iconify from '@/components/iconify/Iconify'
import Label from '@/components/label/Label'

const DENSITY_CYCLE: GridDensity[] = ['compact', 'standard', 'comfortable']

const SPINNER_SIZE = 20

interface ListToolbarProps {
  /** The tab label — the collection's name. */
  title: string
  /** Rows on the current page; shown as the tab's count badge. */
  count: number
  addLabel: string
  onAdd: () => void
  density: GridDensity
  onDensityChange: (density: GridDensity) => void
  onRefresh: () => void
  refreshing: boolean
  densityLabel: string
  refreshLabel: string
}

export default function ListToolbar({
  title,
  count,
  addLabel,
  onAdd,
  density,
  onDensityChange,
  onRefresh,
  refreshing,
  densityLabel,
  refreshLabel,
}: ListToolbarProps) {
  const nextDensity = DENSITY_CYCLE[(DENSITY_CYCLE.indexOf(density) + 1) % DENSITY_CYCLE.length]

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
        direction="row"
        alignItems="center"
        justifyContent="space-between"
        sx={{ px: 2.5, py: 2 }}
      >
        <Button
          variant="contained"
          startIcon={<Iconify name="add" />}
          onClick={onAdd}
        >
          {addLabel}
        </Button>

        <Stack direction="row" spacing={0.5}>
          <Tooltip title={densityLabel}>
            <IconButton onClick={() => onDensityChange(nextDensity)}>
              <Iconify name="density" />
            </IconButton>
          </Tooltip>
          <Tooltip title={refreshLabel}>
            <IconButton onClick={onRefresh} disabled={refreshing}>
              {refreshing ? (
                <CircularProgress size={SPINNER_SIZE} />
              ) : (
                <Iconify name="refresh" />
              )}
            </IconButton>
          </Tooltip>
        </Stack>
      </Stack>
    </>
  )
}
