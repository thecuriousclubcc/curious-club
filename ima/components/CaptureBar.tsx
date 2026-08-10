'use client'

import { useCallback, useRef, useState } from 'react'
import { capture } from '@/lib/db'
import { t, type Locale } from '@/lib/i18n'
import { btn, btnPrimary, input } from './ui'

// Minimal shape of the Web Speech API. Android Chrome has it; it needs network
// for recognition, so typing always stays available alongside it.
type Recognition = {
  lang: string
  interimResults: boolean
  continuous: boolean
  start: () => void
  stop: () => void
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null
  onend: (() => void) | null
  onerror: (() => void) | null
}

type RecognitionCtor = new () => Recognition

function recognitionCtor(): RecognitionCtor | undefined {
  if (typeof window === 'undefined') return undefined
  const w = window as unknown as {
    SpeechRecognition?: RecognitionCtor
    webkitSpeechRecognition?: RecognitionCtor
  }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition
}

export function CaptureBar({
  locale,
  autoFocus = false,
  onCaptured,
}: {
  locale: Locale
  autoFocus?: boolean
  onCaptured?: () => void
}) {
  const [text, setText] = useState('')
  const [listening, setListening] = useState(false)
  const recognition = useRef<Recognition | null>(null)

  const submit = useCallback(
    async (value: string) => {
      const id = await capture(value)
      if (id !== undefined) {
        setText('')
        onCaptured?.()
      }
    },
    [onCaptured],
  )

  const listen = useCallback(() => {
    const Ctor = recognitionCtor()
    if (!Ctor) return
    const rec = new Ctor()
    recognition.current = rec
    rec.lang = locale === 'ja' ? 'ja-JP' : 'en-US'
    rec.interimResults = false
    rec.continuous = false
    rec.onresult = (event) => {
      const said = event.results[0]?.[0]?.transcript ?? ''
      // Straight in, no confirmation step — a confirm dialog is where a
      // captured thought goes to die.
      if (said.trim()) void submit(said)
    }
    rec.onend = () => setListening(false)
    rec.onerror = () => setListening(false)
    setListening(true)
    rec.start()
  }, [locale, submit])

  const hasVoice = recognitionCtor() !== undefined

  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={(event) => {
        event.preventDefault()
        void submit(text)
      }}
    >
      <input
        className={input}
        value={text}
        // Focused on the capture screen only, which exists purely to catch a
        // thought before working memory drops it.
        autoFocus={autoFocus}
        onChange={(event) => setText(event.target.value)}
        placeholder={t(locale, 'capture.placeholder')}
        enterKeyHint="done"
        aria-label={t(locale, 'capture.placeholder')}
      />
      <div className="flex gap-2">
        <button type="submit" className={`${btnPrimary} flex-1`} disabled={!text.trim()}>
          {t(locale, 'capture.add')}
        </button>
        {hasVoice ? (
          <button type="button" className={btn} onClick={listen} aria-pressed={listening}>
            {listening ? t(locale, 'capture.listening') : t(locale, 'capture.voice')}
          </button>
        ) : null}
      </div>
    </form>
  )
}
