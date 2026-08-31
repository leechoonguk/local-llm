/**
 * Route component for the integration domain.
 */

import { useTranslation } from 'react-i18next'
import IntegrationList from '@/sections/integration/IntegrationList'
import PageHeader from '@/components/page-header/PageHeader'
import { PATHS } from '@/routes/paths'

export default function IntegrationPage() {
  const { t } = useTranslation('integration')
  const { t: tNav } = useTranslation('nav')

  return (
    <>
      <PageHeader
        heading={t('title')}
        description={t('description')}
        links={[{ label: tNav('dashboard'), href: PATHS.dashboard }, { label: t('title') }]}
      />
      <IntegrationList />
    </>
  )
}
