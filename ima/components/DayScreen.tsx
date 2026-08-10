'use client'

import type { Task } from '@/lib/db'
import { doneOn, upcomingDeadlines } from '@/lib/tasks'
import { t, type Locale } from '@/lib/i18n'
import { card, label, screen } from './ui'

export function DayScreen({ tasks, locale }: { tasks: Task[]; locale: Locale }) {
  const now = new Date()
  const deadlines = upcomingDeadlines(tasks, now)
  const finished = doneOn(tasks, now)
  const tag = locale === 'ja' ? 'ja-JP' : 'en-GB'

  return (
    <div className={screen}>
      <p className={label}>{t(locale, 'day.deadlines')}</p>
      {deadlines.length === 0 ? (
        <p className="text-sm text-muted">{t(locale, 'day.none')}</p>
      ) : (
        <ul className="flex flex-col gap-row">
          {deadlines.map((task) => (
            <li key={task.id} className={`${card} flex items-baseline gap-3 p-3`}>
              <span className="font-display text-xs tabular-nums text-caution">
                {new Date(task.hardDeadline ?? 0).toLocaleString(tag, {
                  weekday: 'short',
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
              <span className="text-base text-ink">{task.title}</span>
            </li>
          ))}
        </ul>
      )}

      <p className={`${label} mt-8`}>{t(locale, 'day.finished')}</p>
      {finished.length === 0 ? (
        <p className="text-sm text-muted">{t(locale, 'empty.log')}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {finished.map((task) => (
            <li key={task.id} className="flex items-baseline gap-3">
              <span className="font-display text-xs tabular-nums text-ok">
                {new Date(task.doneAt ?? 0).toLocaleTimeString(tag, {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
              <span className="text-base text-muted">{task.title}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
