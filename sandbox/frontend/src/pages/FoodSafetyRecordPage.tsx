/**
 * Route component for the event list.
 */

import { useTranslation } from 'react-i18next'
import PageHeader from '@/components/page-header/PageHeader'
import FoodSafetyRecordDerivedList from '@/sections/food/FoodSafetyRecordDerivedList'
import { PATHS } from '@/routes/paths'

export default function FoodSafetyRecordPage() {
  const { t } = useTranslation('food')
  const { t: tNav } = useTranslation('nav')

  return (
    <>
      <PageHeader
        heading={t('item_report.event.list_title')}
        description={t('item_report.event.description')}
        links={[
          { label: tNav('dashboard'), href: PATHS.dashboard },
          { label: tNav('group.food') },
          { label: t('item_report.event.list_title') },
        ]}
      />
      <FoodSafetyRecordDerivedList />
    </>
  )
}
