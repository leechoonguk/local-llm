/**
 * The provider's operations, as a paged table inside the detail dialog.
 *
 * A tab is a pure presenter: it takes the rows it was handed and queries nothing.
 * Every action opens a panel one level up — the dialog owns the mutation, and the
 * tab owns nothing but the reading of it. The frame is `PagedTableSection`; what
 * is local here is the columns and what a row draws.
 *
 * Declared shares, so the code column does not shrink to whatever the longest
 * path leaves behind. The path is the long value and the one worth clipping: it is
 * the same template on every row, while a code is the row's identity.
 */

import { TableCell } from '@mui/material'
import { useTranslation } from 'react-i18next'
import PagedTableSection from '@/components/detail/PagedTableSection'
import type { TableColumn } from '@/components/detail/PagedTableSection'
import ClippedText from '@/components/detail/ClippedText'
import Label from '@/components/label/Label'
import { RECORD_SURFACE } from '@/config'
import type { TablePaging } from '@/hooks/useTablePage'
import type { IntegrationOperation } from '@/types/integration'

const ACTIONS_WIDTH = RECORD_SURFACE.TABLE_ACTIONS_WIDTH

export default function IntegrationOperationsTab({
  paging,
  onCreate,
  onSelect,
  onDelete,
}: {
  /**
   * The page is the dialog's state: opening a record replaces this body, so a
   * page held here would be lost on every visit to a record.
   */
  paging: TablePaging<IntegrationOperation>
  onCreate: () => void
  onSelect: (operation: IntegrationOperation) => void
  onDelete: (operation: IntegrationOperation) => void
}) {
  const { t } = useTranslation('integration')
  const { t: tCommon } = useTranslation('common')

  const columns: TableColumn[] = [
    { key: 'method', label: t('operation.method'), width: '9%' },
    { key: 'code', label: t('operation.code'), width: '23%' },
    { key: 'path', label: t('operation.path_template'), width: '40%' },
    { key: 'fieldCount', label: t('operation.field_count'), width: '7%', align: 'center' },
    { key: 'enabled', label: t('table.enabled'), width: '11%', align: 'center' },
  ]

  return (
    <PagedTableSection
      icon="link"
      title={t('tabs.operations')}
      onCreate={onCreate}
      columns={columns}
      actionsWidth={ACTIONS_WIDTH}
      paging={paging}
      rowKey={(operation) => operation.id}
      renderCells={(operation) => (
        <>
          <TableCell>
            <Label color="info">{operation.method}</Label>
          </TableCell>
          <TableCell>
            <ClippedText text={operation.code} />
          </TableCell>
          <TableCell>
            <ClippedText text={operation.path_template} />
          </TableCell>
          <TableCell align="center">
            <ClippedText text={String(operation.fields.length)} />
          </TableCell>
          <TableCell align="center">
            <Label variant="soft" color={operation.enabled ? 'success' : 'default'}>
              {operation.enabled ? tCommon('status.enabled') : tCommon('status.disabled')}
            </Label>
          </TableCell>
        </>
      )}
      actions={(operation) => [
        {
          label: tCommon('actions.view'),
          icon: 'view',
          onClick: () => onSelect(operation),
        },
        {
          label: tCommon('actions.delete'),
          icon: 'delete',
          tone: 'error',
          onClick: () => onDelete(operation),
        },
      ]}
    />
  )
}
