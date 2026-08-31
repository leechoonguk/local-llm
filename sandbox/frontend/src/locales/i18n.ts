/**
 * i18n initialisation.
 *
 * Korean is both the default and the fallback: this is a Korean-first product,
 * so an untranslated English key must fall back to text a user can read rather
 * than to the key itself. Interpolation escaping is off because React already
 * escapes everything it renders — leaving it on double-escapes names.
 */

import i18next from 'i18next'
import { initReactI18next } from 'react-i18next'
import { en } from '@/locales/en'
import { ko } from '@/locales/ko'

export const DEFAULT_LANGUAGE = 'ko'

export const SUPPORTED_LANGUAGES = ['ko', 'en'] as const

void i18next.use(initReactI18next).init({
  resources: { ko, en },
  lng: DEFAULT_LANGUAGE,
  fallbackLng: DEFAULT_LANGUAGE,
  defaultNS: 'common',
  interpolation: { escapeValue: false },
})

export default i18next
