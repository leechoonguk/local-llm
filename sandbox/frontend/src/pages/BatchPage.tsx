/**
 * Route component for the batch domain.
 */

import { useTranslation } from 'react-i18next'
import BatchList from '@/sections/batch/BatchList'
import PageHeader from '@/components/page-header/PageHeader'
import { PATHS } from '@/routes/paths'

export default function BatchPage() {
  const { t } = useTranslation('batch')
  const { t: tNav } = useTranslation('nav')

  return (
    <>
      <PageHeader
        heading={t('title')}
        description={t('description')}
        links={[{ label: tNav('dashboard'), href: PATHS.dashboard }, { label: t('title') }]}
      />
      <BatchList />
    </>
  )
}
