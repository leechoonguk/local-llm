/**
 * The material's composition siblings - every code of the same base, the one
 * open included, in code order.
 *
 * A tab is a pure presenter: it takes the rows it was handed and queries
 * nothing. No add and no actions: the table is rebuilt off the ledger nightly.
 */

import { TableCell } from '@mui/material'
import { useTranslation } from 'react-i18next'
import ClippedText from '@/components/detail/ClippedText'
import PagedTableSection from '@/components/detail/PagedTableSection'
import type { TableColumn } from '@/components/detail/PagedTableSection'
import type { TablePaging } from '@/hooks/useTablePage'
import type { FoodRawMaterial } from '@/types/food'

export default function FoodRawMaterialVariantsTab({
  paging,
}: {
  /** The page is the dialog's state: switching tabs unmounts this body. */
  paging: TablePaging<FoodRawMaterial>
}) {
  const { t } = useTranslation('food')

  const columns: TableColumn[] = [
    { key: 'code', label: t('raw_material.table.code'), width: '24%' },
    { key: 'name', label: t('raw_material.table.name'), width: '34%' },
    { key: 'region', label: t('raw_material.table.region'), width: '14%' },
    { key: 'process', label: t('raw_material.table.process'), width: '14%' },
    { key: 'status', label: t('raw_material.table.status'), width: '14%' },
  ]

  return (
    <PagedTableSection
      icon="layers"
      title={t('raw_material.tabs.variants')}
      columns={columns}
      paging={paging}
      rowKey={(variant) => variant.id}
      renderCells={(variant) => (
        <>
          <TableCell>
            <ClippedText text={variant.raw_material_code} />
          </TableCell>
          <TableCell>
            <ClippedText text={variant.representative_raw_material_name ?? '—'} />
          </TableCell>
          <TableCell>
            <ClippedText text={variant.region_code_name ?? '—'} />
          </TableCell>
          <TableCell>
            <ClippedText text={variant.process_code_name ?? '—'} />
          </TableCell>
          <TableCell>
            <ClippedText text={variant.raw_material_status_code_name ?? '—'} />
          </TableCell>
        </>
      )}
    />
  )
}
