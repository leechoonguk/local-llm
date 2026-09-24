/**
 * Route component for the food chat.
 */

import { useTranslation } from 'react-i18next'
import PageHeader from '@/components/page-header/PageHeader'
import FoodChatConversation from '@/sections/food/FoodChatConversation'
import { PATHS } from '@/routes/paths'

export default function FoodChatPage() {
  const { t } = useTranslation('food')
  const { t: tNav } = useTranslation('nav')

  return (
    <>
      <PageHeader
        heading={t('chat.title')}
        description={t('chat.description')}
        links={[
          { label: tNav('dashboard'), href: PATHS.dashboard },
          { label: tNav('group.food') },
          { label: t('chat.title') },
        ]}
      />
      <FoodChatConversation />
    </>
  )
}
