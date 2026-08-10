'use client'

import { useCallback, useEffect, useState } from 'react'
import { THEMES } from '@/lib/themes'
import { resolveRotation } from '@/lib/rotation'
import { applyTheme } from '@/lib/apply-theme'
import { PREF_KEYS, readPref, writePref } from '@/lib/prefs'
import type { Locale } from '@/lib/i18n'
import { usePref } from './usePref'

export function useSettings() {
  const storedLocale = usePref(PREF_KEYS.locale, 'ja')
  const locale: Locale = storedLocale === 'en' ? 'en' : 'ja'
  const pin = usePref(PREF_KEYS.pin, '')
  const shuffle = Number.parseInt(usePref(PREF_KEYS.shuffle, '0'), 10) || 0
  const seen = usePref(PREF_KEYS.seen, '')

  // Minute tick, so a 4am flip lands even if the app was left open overnight.
  const [, tick] = useState(0)
  useEffect(() => {
    const id = window.setInterval(() => tick((n) => n + 1), 60_000)
    return () => window.clearInterval(id)
  }, [])

  const rotation = resolveRotation(new Date(), {
    pinnedId: pin || null,
    shuffleOffset: shuffle,
  })

  // Pushing the token set onto <html> is exactly what an effect is for: keeping
  // an external system in step with React state.
  useEffect(() => {
    applyTheme(rotation.theme)
  }, [rotation.theme])

  // First open on a new skin gets a brief reveal, so the change reads as a
  // small event rather than "did something break?". `seen` is stored, not held
  // in state, so hiding the banner is a store write rather than a setState
  // buried in an effect.
  const showReveal = seen !== '' && seen !== rotation.theme.id

  useEffect(() => {
    if (seen === rotation.theme.id) return
    if (seen === '') {
      // First ever launch: record the skin, don't announce it.
      writePref(PREF_KEYS.seen, rotation.theme.id)
      return
    }
    const id = window.setTimeout(() => writePref(PREF_KEYS.seen, rotation.theme.id), 2600)
    return () => window.clearTimeout(id)
  }, [seen, rotation.theme.id])

  const changeLocale = useCallback((next: Locale) => {
    writePref(PREF_KEYS.locale, next)
  }, [])

  const togglePin = useCallback(() => {
    writePref(PREF_KEYS.pin, readPref(PREF_KEYS.pin) ? null : rotation.theme.id)
  }, [rotation.theme.id])

  /** Advance to the next skin early, for when today's simply grates. */
  const shuffleNow = useCallback(() => {
    writePref(PREF_KEYS.pin, null)
    const current = Number.parseInt(readPref(PREF_KEYS.shuffle) ?? '0', 10) || 0
    writePref(PREF_KEYS.shuffle, String(current + 1))
  }, [])

  return {
    locale,
    changeLocale,
    rotation,
    pinned: Boolean(pin),
    togglePin,
    shuffleNow,
    showReveal,
    themeCount: THEMES.length,
  }
}
