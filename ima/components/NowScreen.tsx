'use client'

import { useState } from 'react'
import type { Task } from '@/lib/db'
import { complete, endSession, setFirstStep, snooze, startSession } from '@/lib/db'
import { isUrgent, needsFirstStep, pickNow } from '@/lib/tasks'
import { emptyLine, t, type Locale } from '@/lib/i18n'
import type { Theme } from '@/lib/themes'
import { Timer } from './Timer'
import { btn, btnPrimary, btnQuiet, input, label, screen } from './ui'

const DIRTY_MS = 5 * 60 * 1000

export function NowScreen({
  tasks,
  locale,
  theme,
  slot,
  onDrop,
}: {
  tasks: Task[]
  locale: Locale
  theme: Theme
  slot: number
  onDrop: (task: Task) => void
}) {
  const now = new Date()
  const task = pickNow(tasks, now)

  const [sessionId, setSessionId] = useState<number | null>(null)
  const [finished, setFinished] = useState(false)
  const [draft, setDraft] = useState('')

  const stop = async () => {
    if (sessionId !== null) await endSession(sessionId)
    setSessionId(null)
    setFinished(false)
  }

  if (!task) {
    return (
      <div className={screen}>
        <p className="mt-16 text-center font-display text-xl text-muted">
          {emptyLine(theme.voice, locale, slot)}
        </p>
      </div>
    )
  }

  const urgent = isUrgent(task, now)

  // A task with no physical first step isn't startable, so NOW asks for one
  // instead of offering a fog to walk into.
  if (needsFirstStep(task)) {
    return (
      <div className={screen}>
        <p className={label}>{t(locale, 'tab.now')}</p>
        <h1 className="font-display text-2xl leading-snug text-ink [text-wrap:balance]">
          {task.title}
        </h1>
        <div className="mt-4 flex flex-col gap-2">
          <p className="font-display text-lg text-ink">{t(locale, 'now.firstStepPrompt')}</p>
          <p className="text-sm text-muted">{t(locale, 'now.firstStepHelp')}</p>
          <input
            className={input}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={t(locale, 'now.firstStepPlaceholder')}
            aria-label={t(locale, 'now.firstStepPrompt')}
          />
          <button
            type="button"
            className={btnPrimary}
            disabled={!draft.trim()}
            onClick={() => {
              if (task.id !== undefined) void setFirstStep(task.id, draft)
              setDraft('')
            }}
          >
            {t(locale, 'now.firstStepSave')}
          </button>
          <button
            type="button"
            className={btnQuiet}
            onClick={() => task.id !== undefined && void snooze(task.id)}
          >
            {t(locale, 'now.notNow')}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className={screen}>
      <p className={label}>{t(locale, 'tab.now')}</p>

      {urgent && task.hardDeadline !== undefined ? (
        <p className="font-display text-xs uppercase tracking-widest text-caution">
          {t(locale, 'now.deadline')}{' '}
          {new Date(task.hardDeadline).toLocaleString(locale === 'ja' ? 'ja-JP' : 'en-GB', {
            weekday: 'short',
            hour: '2-digit',
            minute: '2-digit',
          })}
        </p>
      ) : null}

      <h1 className="font-display text-[1.75rem] leading-snug text-ink [text-wrap:balance]">
        {task.title}
      </h1>

      {task.firstStep ? (
        <p className="border-l-2 border-accent pl-3 text-base text-muted">{task.firstStep}</p>
      ) : null}

      <div className="mt-6 flex flex-col gap-2">
        {sessionId !== null && !finished ? (
          <Timer
            durationMs={DIRTY_MS}
            locale={locale}
            onFinish={() => setFinished(true)}
            onStop={() => void stop()}
          />
        ) : (
          <>
            {finished ? (
              <p className="font-display text-sm text-ok">
                {locale === 'ja' ? '5分やりました。' : 'Five minutes done.'}
              </p>
            ) : null}
            <button
              type="button"
              className={btnPrimary}
              onClick={async () => {
                if (task.id === undefined) return
                setFinished(false)
                setSessionId(await startSession(task.id, 'dirty'))
              }}
            >
              {t(locale, 'now.start')}
            </button>
            <p className="text-center text-xs text-muted">{t(locale, 'now.startHint')}</p>
          </>
        )}

        <div className="mt-2 flex gap-2">
          <button
            type="button"
            className={`${btn} flex-1`}
            onClick={async () => {
              if (task.id === undefined) return
              await stop()
              await complete(task.id)
            }}
          >
            {t(locale, 'now.done')}
          </button>
          <button
            type="button"
            className={`${btn} flex-1`}
            onClick={async () => {
              if (task.id === undefined) return
              await stop()
              await snooze(task.id)
            }}
          >
            {t(locale, 'now.notNow')}
          </button>
        </div>

        <button
          type="button"
          className={btnQuiet}
          onClick={async () => {
            await stop()
            onDrop(task)
          }}
        >
          {t(locale, 'now.nope')}
        </button>
      </div>
    </div>
  )
}
