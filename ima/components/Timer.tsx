'use client'

import { useEffect, useRef, useState } from 'react'
import { t, type Locale } from '@/lib/i18n'
import { btn } from './ui'

/**
 * A draining bar, not a countdown. The shape of the remaining time is legible
 * at a glance in a way that `04:12` never is — digits are there, but small and
 * secondary.
 */
export function Timer({
  durationMs,
  locale,
  onFinish,
  onStop,
}: {
  durationMs: number
  locale: Locale
  onFinish: () => void
  onStop: () => void
}) {
  const [remaining, setRemaining] = useState(durationMs)

  // Held in a ref so the countdown does not restart every time the parent
  // re-renders with a fresh callback identity.
  const finish = useRef(onFinish)
  useEffect(() => {
    finish.current = onFinish
  }, [onFinish])

  useEffect(() => {
    const startedAt = Date.now()
    const id = window.setInterval(() => {
      const left = durationMs - (Date.now() - startedAt)
      if (left <= 0) {
        setRemaining(0)
        window.clearInterval(id)
        finish.current()
      } else {
        setRemaining(left)
      }
    }, 250)
    return () => window.clearInterval(id)
  }, [durationMs])

  const fraction = Math.max(0, remaining / durationMs)
  const seconds = Math.ceil(remaining / 1000)
  const mm = Math.floor(seconds / 60)
  const ss = String(seconds % 60).padStart(2, '0')

  return (
    <div className="flex flex-col gap-3">
      <div
        className="h-6 w-full overflow-hidden rounded-token border-token border-hairline bg-surface"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={durationMs}
        aria-valuenow={remaining}
      >
        <div
          className="h-full bg-accent"
          style={{ width: `${fraction * 100}%`, transition: 'width 250ms linear' }}
        />
      </div>
      <div className="flex items-center justify-between">
        <span className="font-display text-sm tabular-nums text-muted">
          {mm}:{ss} {t(locale, 'now.timeLeft')}
        </span>
        <button type="button" className={btn} onClick={onStop}>
          {t(locale, 'now.stop')}
        </button>
      </div>
    </div>
  )
}
