/**
 * The report's label - its ingredients in the order the portal lists them.
 *
 * A tab is a pure presenter: it takes the rows it was handed and queries
 * nothing. No add and no actions: the split is rebuilt off the ledger nightly.
 */

import { Stack, TableCell } from '@mui/material'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import ClippedText from '@/components/detail/ClippedText'
import Label from '@/components/label/Label'
import PagedTableSection from '@/components/detail/PagedTableSection'
import type { TableColumn } from '@/components/detail/PagedTableSection'
import type { TablePaging } from '@/hooks/useTablePage'
import type { FoodItemReportIngredient } from '@/types/food'

/**
 * The three roles 건강기능식품 publishes, and the colour each reads as. The
 * other three registries publish one list and no role, so a row without one
 * shows its name alone rather than a badge saying "ingredient".
 */
const ROLE_COLOUR = { functional: 'success', other: 'default', capsule: 'info' } as const

type IngredientRole = keyof typeof ROLE_COLOUR

export default function FoodItemReportIngredientsTab({
  paging,
}: {
  /** The page is the dialog's state: switching tabs unmounts this body. */
  paging: TablePaging<FoodItemReportIngredient>
}) {
  const { t } = useTranslation('food')

  const columns: TableColumn[] = [
    { key: 'position', label: t('item_report.ingredient.position'), width: '12%', align: 'center' },
    { key: 'ordinal', label: t('item_report.ingredient.ordinal'), width: '18%', align: 'center' },
    { key: 'name', label: t('item_report.ingredient.name'), width: '70%' },
  ]

  return (
    <PagedTableSection
      icon="layers"
      title={t('item_report.tabs.ingredients')}
      columns={columns}
      paging={paging}
      rowKey={(ingredient) => ingredient.id}
      renderCells={(ingredient) => (
        <>
          <TableCell align="center">
            <ClippedText text={String(ingredient.position)} />
          </TableCell>
          <TableCell align="center">
            <ClippedText text={ingredient.ordinal === null ? '—' : String(ingredient.ordinal)} />
          </TableCell>
          <TableCell>
            <Stack direction="row" alignItems="center" spacing={1}>
              <ClippedText text={ingredient.name} />
              {renderRole(ingredient.ingredient_role, t)}
            </Stack>
          </TableCell>
        </>
      )}
    />
  )
}

// ============================================================
// Functions
// ============================================================

/** A row's role as a badge, and nothing at all when the registry publishes none. */
function renderRole(value: string | null, t: TFunction<'food'>) {
  if (value === null || !(value in ROLE_COLOUR)) return null
  const name = value as IngredientRole
  return (
    <Label variant="soft" color={ROLE_COLOUR[name]}>
      {t(`item_report.ingredient.role.${name}`)}
    </Label>
  )
}
