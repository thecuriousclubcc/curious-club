'use client'

import { useSyncExternalStore } from 'react'
import { PREF_KEYS, readPref, subscribePrefs } from '@/lib/prefs'
import type { Locale } from '@/lib/i18n'

/** Read a stored preference during render, without copying it into state. */
export function usePref(key: string, fallback: string): string {
  return useSyncExternalStore(
    subscribePrefs,
    () => readPref(key) ?? fallback,
    () => fallback,
  )
}

export function useLocale(): Locale {
  return usePref(PREF_KEYS.locale, 'ja') === 'en' ? 'en' : 'ja'
}
