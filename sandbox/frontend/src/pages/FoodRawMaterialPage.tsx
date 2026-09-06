/**
 * Route component for the raw material ledger.
 */

import { useTranslation } from 'react-i18next'
import PageHeader from '@/components/page-header/PageHeader'
import FoodRawMaterialLedgerList from '@/sections/food/FoodRawMaterialLedgerList'
import { PATHS } from '@/routes/paths'

export default function FoodRawMaterialPage() {
  const { t } = useTranslation('food')
  const { t: tNav } = useTranslation('nav')

  return (
    <>
      <PageHeader
        heading={t('raw_material.title')}
        description={t('raw_material.description')}
        links={[
          { label: tNav('dashboard'), href: PATHS.dashboard },
          { label: tNav('group.food') },
          { label: t('raw_material.title') },
        ]}
      />
      <FoodRawMaterialLedgerList />
    </>
  )
}
