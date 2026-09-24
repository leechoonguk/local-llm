/**
 * The rows this business shares a name or a site with - candidates, not owners.
 *
 * Nothing public keys a licence to a 법인등록번호 (measured 2026-09-23 across
 * 식약처, LOCALDATA and 국민연금), so a shared name is a shared spelling and
 * nothing more: `우리식품` is 164 licences across 100 districts. A shared site
 * is stronger but rarer - the GIS ledger answers a building or a parcel for
 * 21.7 % of the live rows, and 2,019 sites hold more than one licence.
 *
 * A tab is a pure presenter: it takes the rows it was handed and queries nothing.
 */

import { TableCell } from '@mui/material'
import { useTranslation } from 'react-i18next'
import ClippedText from '@/components/detail/ClippedText'
import Label from '@/components/label/Label'
import PagedTableSection from '@/components/detail/PagedTableSection'
import type { TableColumn } from '@/components/detail/PagedTableSection'
import type { ActionIcon } from '@/components/iconify/icons'
import type { TablePaging } from '@/hooks/useTablePage'
import type { FoodBusiness } from '@/types/food'

export default function FoodBusinessRelatedTab({
  icon,
  title,
  paging,
}: {
  icon: ActionIcon
  title: string
  /** The page is the dialog's state: switching tabs unmounts this body. */
  paging: TablePaging<FoodBusiness>
}) {
  const { t } = useTranslation('food')

  const columns: TableColumn[] = [
    { key: 'license_no', label: t('business.table.license_no'), width: '22%' },
    { key: 'business_name', label: t('business.table.business_name'), width: '30%' },
    { key: 'industry_name', label: t('business.table.industry_name'), width: '22%' },
    { key: 'status', label: t('business.table.status'), width: '12%' },
    { key: 'district', label: t('business.table.district'), width: '14%' },
  ]

  return (
    <PagedTableSection
      icon={icon}
      title={title}
      columns={columns}
      paging={paging}
      rowKey={(business) => business.id}
      renderCells={(business) => (
        <>
          <TableCell>
            <ClippedText text={business.license_no} />
          </TableCell>
          <TableCell>
            <ClippedText text={business.business_name ?? '—'} />
          </TableCell>
          <TableCell>
            <ClippedText text={business.industry_name ?? '—'} />
          </TableCell>
          <TableCell>
            <Label variant="soft" color={business.status === 'ACTIVE' ? 'success' : 'default'}>
              {t(`business.status.${business.status}`)}
            </Label>
          </TableCell>
          <TableCell>
            <ClippedText text={business.district ?? '—'} />
          </TableCell>
        </>
      )}
    />
  )
}
