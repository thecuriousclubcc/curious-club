'use client'

import { Suspense, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { capture } from '@/lib/db'
import { t } from '@/lib/i18n'
import { CaptureBar } from '@/components/CaptureBar'
import { useLocale } from '@/components/usePref'
import { btn, label } from '@/components/ui'

/**
 * The fast path in: the long-press shortcut on the home icon, and the Android
 * share sheet. Working memory drops a thought in the seconds it takes to open
 * an app and find the right screen, so this opens straight onto a focused text
 * field and needs no navigation at all.
 */
function Capture() {
  const params = useSearchParams()
  const locale = useLocale()
  const [saved, setSaved] = useState(0)
  const handled = useRef<string | null>(null)

  // Anything arriving from the share sheet is captured without a confirmation
  // step — the share itself was the decision.
  useEffect(() => {
    const shared = [params.get('title'), params.get('text'), params.get('url')]
      .filter(Boolean)
      .join(' ')
      .trim()
    if (!shared || handled.current === shared) return
    handled.current = shared
    void capture(shared).then((id) => {
      if (id !== undefined) setSaved((n) => n + 1)
    })
  }, [params])

  return (
    <main className="mx-auto flex max-w-xl flex-col gap-4 px-gutter py-8">
      <p className={label}>{t(locale, 'capture.add')}</p>
      <CaptureBar locale={locale} autoFocus onCaptured={() => setSaved((n) => n + 1)} />
      {saved > 0 ? (
        <p className="font-display text-sm text-ok" role="status">
          {t(locale, 'capture.saved')}
        </p>
      ) : null}
      <Link href="/" className={`${btn} mt-4`}>
        {t(locale, 'tab.now')}
      </Link>
    </main>
  )
}

export default function CapturePage() {
  return (
    <Suspense>
      <Capture />
    </Suspense>
  )
}
