/**
 * Route component for the licensed business list.
 */

import { useTranslation } from 'react-i18next'
import PageHeader from '@/components/page-header/PageHeader'
import FoodBusinessDerivedList from '@/sections/food/FoodBusinessDerivedList'
import { PATHS } from '@/routes/paths'

export default function FoodBusinessPage() {
  const { t } = useTranslation('food')
  const { t: tNav } = useTranslation('nav')

  return (
    <>
      <PageHeader
        heading={t('business.title')}
        description={t('business.description')}
        links={[
          { label: tNav('dashboard'), href: PATHS.dashboard },
          { label: tNav('group.food') },
          { label: t('business.title') },
        ]}
      />
      <FoodBusinessDerivedList />
    </>
  )
}
