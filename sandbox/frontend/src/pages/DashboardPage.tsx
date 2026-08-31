/**
 * Route component — the header, and the section that does the work.
 *
 * A page is deliberately thin: it names the screen, builds the breadcrumb from
 * the path registry and renders one section. Data fetching lives in the
 * section, so a route change never has to move a query.
 */

import { useTranslation } from 'react-i18next'
import PageHeader from '@/components/page-header/PageHeader'
import DashboardView from '@/sections/dashboard/DashboardView'
import { PATHS } from '@/routes/paths'

export default function DashboardPage() {
  const { t } = useTranslation('dashboard')

  return (
    <>
      <PageHeader
        heading={t('title')}
        description={t('description')}
        links={[{ label: t('title'), href: PATHS.dashboard }]}
      />
      <DashboardView />
    </>
  )
}
