/**
 * Route component for the user domain.
 */

import { useTranslation } from 'react-i18next'
import PageHeader from '@/components/page-header/PageHeader'
import UserList from '@/sections/user/UserList'
import { PATHS } from '@/routes/paths'

export default function UserPage() {
  const { t } = useTranslation('user')
  const { t: tNav } = useTranslation('nav')

  return (
    <>
      <PageHeader
        heading={t('title')}
        description={t('description')}
        links={[{ label: tNav('dashboard'), href: PATHS.dashboard }, { label: t('title') }]}
      />
      <UserList />
    </>
  )
}
