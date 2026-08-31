/**
 * The provider's named credentials, without their values.
 *
 * `IntegrationSecretReadResponse` has no `value` field, and that is the point: the
 * value goes in and never comes back out. That fact is not a banner here — an
 * always-true `Alert` sits in the band where real messages appear and teaches the
 * reader to skip it. It lives under the masked value inside the record, which is
 * the only place anyone looks for a key they cannot find.
 *
 * The frame is `PagedTableSection`, shared with the operations tab; what is local
 * is the columns and the cells.
 */

import { TableCell } from '@mui/material'
import { useTranslation } from 'react-i18next'
import PagedTableSection from '@/components/detail/PagedTableSection'
import type { TableColumn } from '@/components/detail/PagedTableSection'
import ClippedText from '@/components/detail/ClippedText'
import Label from '@/components/label/Label'
import type { TablePaging } from '@/hooks/useTablePage'
import { RECORD_SURFACE } from '@/config'
import { formatDateTime } from '@/utils/formatTime'
import type { IntegrationSecret } from '@/types/integration'

const ACTIONS_WIDTH = RECORD_SURFACE.TABLE_ACTIONS_WIDTH

export default function IntegrationSecretsTab({
  paging,
  onCreate,
  onSelect,
  onDelete,
}: {
  /** The page survives a visit to a record because the dialog holds it. */
  paging: TablePaging<IntegrationSecret>
  onCreate: () => void
  onSelect: (secret: IntegrationSecret) => void
  onDelete: (secret: IntegrationSecret) => void
}) {
  const { t } = useTranslation('integration')
  const { t: tCommon } = useTranslation('common')

  const columns: TableColumn[] = [
    { key: 'name', label: t('secret.name'), width: '24%' },
    { key: 'description', label: t('secret.description'), width: '40%' },
    { key: 'enabled', label: t('table.enabled'), width: '11%', align: 'center' },
    { key: 'createdAt', label: tCommon('fields.created_at'), width: '15%' },
  ]

  return (
    <PagedTableSection
      icon="lock"
      title={t('tabs.secrets')}
      onCreate={onCreate}
      columns={columns}
      actionsWidth={ACTIONS_WIDTH}
      paging={paging}
      rowKey={(secret) => secret.id}
      renderCells={(secret) => (
        <>
          <TableCell>
            <ClippedText text={secret.name} />
          </TableCell>
          <TableCell>
            <ClippedText text={secret.description ?? '-'} />
          </TableCell>
          <TableCell align="center">
            <Label variant="soft" color={secret.enabled ? 'success' : 'default'}>
              {secret.enabled ? tCommon('status.enabled') : tCommon('status.disabled')}
            </Label>
          </TableCell>
          <TableCell>
            <ClippedText text={formatDateTime(secret.created_at)} />
          </TableCell>
        </>
      )}
      actions={(secret) => [
        {
          label: tCommon('actions.view'),
          icon: 'view',
          onClick: () => onSelect(secret),
        },
        {
          label: tCommon('actions.delete'),
          icon: 'delete',
          tone: 'error',
          onClick: () => onDelete(secret),
        },
      ]}
    />
  )
}
