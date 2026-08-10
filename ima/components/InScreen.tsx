'use client'

import type { Task } from '@/lib/db'
import { amnesty, complete, promote } from '@/lib/db'
import { emptyLine, t, type Locale } from '@/lib/i18n'
import type { Theme } from '@/lib/themes'
import { CaptureBar } from './CaptureBar'
import { btn, btnQuiet, card, label, screen } from './ui'

export function InScreen({
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
  const inbox = tasks
    .filter((task) => task.state === 'inbox')
    .sort((a, b) => b.createdAt - a.createdAt)

  return (
    <div className={screen}>
      <p className={label}>{t(locale, 'in.title')}</p>
      <CaptureBar locale={locale} />

      {inbox.length === 0 ? (
        <p className="mt-10 text-center font-display text-lg text-muted">
          {emptyLine(theme.voice, locale, slot + 1)}
        </p>
      ) : (
        <ul className="flex flex-col gap-row">
          {inbox.map((task) => (
            <li key={task.id} className={`${card} flex flex-col gap-2 p-3`}>
              <p className="text-base text-ink">{task.title}</p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className={btn}
                  onClick={() => task.id !== undefined && void promote(task.id)}
                >
                  {t(locale, 'in.promote')}
                </button>
                <button
                  type="button"
                  className={btn}
                  onClick={() => task.id !== undefined && void complete(task.id)}
                >
                  {t(locale, 'now.done')}
                </button>
                <button type="button" className={btnQuiet} onClick={() => onDrop(task)}>
                  {t(locale, 'now.nope')}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {inbox.length > 0 ? (
        <div className="mt-8 flex flex-col gap-1">
          <button type="button" className={btnQuiet} onClick={() => void amnesty()}>
            {t(locale, 'in.amnesty')}
          </button>
          <p className="text-center text-xs text-muted">{t(locale, 'in.amnestyHint')}</p>
        </div>
      ) : null}
    </div>
  )
}
