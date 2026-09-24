/**
 * Route component for the item report list.
 */

import { useTranslation } from 'react-i18next'
import PageHeader from '@/components/page-header/PageHeader'
import FoodItemReportDerivedList from '@/sections/food/FoodItemReportDerivedList'
import { PATHS } from '@/routes/paths'

export default function FoodItemReportPage() {
  const { t } = useTranslation('food')
  const { t: tNav } = useTranslation('nav')

  return (
    <>
      <PageHeader
        heading={t('item_report.title')}
        description={t('item_report.description')}
        links={[
          { label: tNav('dashboard'), href: PATHS.dashboard },
          { label: tNav('group.food') },
          { label: t('item_report.title') },
        ]}
      />
      <FoodItemReportDerivedList />
    </>
  )
}
