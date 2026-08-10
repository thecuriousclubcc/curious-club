'use client'

import { useMemo, useState } from 'react'
import type { Task } from '@/lib/db'
import { complete, drop, revive } from '@/lib/db'
import { browseModeForSlot } from '@/lib/tasks'
import { emptyLine, t, type Locale } from '@/lib/i18n'
import type { Theme } from '@/lib/themes'
import { btn, btnPrimary, btnQuiet, card, label, screen } from './ui'

/**
 * The full list, behind a deliberate tap. How it is presented rotates with the
 * skin — skin-only novelty goes stale after a couple of cycles. NOW never
 * rotates; this is where the variety lives instead.
 */
export function AllScreen({
  tasks,
  locale,
  theme,
  slot,
}: {
  tasks: Task[]
  locale: Locale
  theme: Theme
  slot: number
}) {
  const mode = browseModeForSlot(slot)
  const live = useMemo(
    () =>
      tasks
        .filter((task) => task.state === 'active' || task.state === 'inbox')
        .sort((a, b) => a.createdAt - b.createdAt),
    [tasks],
  )
  const cold = useMemo(() => tasks.filter((task) => task.state === 'cold'), [tasks])

  const [cursor, setCursor] = useState(0)
  const [spun, setSpun] = useState<number | null>(null)

  const row = (task: Task) => (
    <li key={task.id} className={`${card} flex flex-col gap-2 p-3`}>
      <p className="text-base text-ink">{task.title}</p>
      {task.firstStep ? <p className="text-sm text-muted">{task.firstStep}</p> : null}
      <div className="flex gap-2">
        <button
          type="button"
          className={btn}
          onClick={() => task.id !== undefined && void complete(task.id)}
        >
          {t(locale, 'now.done')}
        </button>
      </div>
    </li>
  )

  return (
    <div className={screen}>
      <div className="flex items-baseline justify-between">
        <p className={label}>{t(locale, 'all.title')}</p>
        <p className={label}>{t(locale, `all.mode.${mode}`)}</p>
      </div>

      {live.length === 0 ? (
        <p className="mt-10 text-center font-display text-lg text-muted">
          {emptyLine(theme.voice, locale, slot + 2)}
        </p>
      ) : mode === 'list' ? (
        <ul className="flex flex-col gap-row">{live.map(row)}</ul>
      ) : mode === 'deck' ? (
        <div className="flex flex-col gap-3">
          <ul className="flex flex-col gap-row">{row(live[cursor % live.length])}</ul>
          <button
            type="button"
            className={btn}
            onClick={() => setCursor((c) => (c + 1) % live.length)}
          >
            {t(locale, 'all.next')}
          </button>
          <p className="text-center font-display text-xs tabular-nums text-muted">
            {(cursor % live.length) + 1} / {live.length}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <button
            type="button"
            className={btnPrimary}
            onClick={() => setSpun(Math.floor(Math.random() * live.length))}
          >
            {t(locale, 'all.spin')}
          </button>
          {spun !== null ? <ul className="flex flex-col gap-row">{row(live[spun % live.length])}</ul> : null}
        </div>
      )}

      {cold.length > 0 ? (
        <>
          <p className={`${label} mt-8`}>{t(locale, 'all.cold')}</p>
          <ul className="flex flex-col gap-row">
            {cold.map((task) => (
              <li key={task.id} className={`${card} flex flex-col gap-2 p-3`}>
                <p className="text-base text-muted">{task.title}</p>
                <p className="text-sm text-muted">{t(locale, 'all.coldPrompt')}</p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    className={btn}
                    onClick={() => task.id !== undefined && void revive(task.id)}
                  >
                    {t(locale, 'all.keep')}
                  </button>
                  <button
                    type="button"
                    className={btnQuiet}
                    onClick={() => task.id !== undefined && void drop(task.id)}
                  >
                    {t(locale, 'all.letGo')}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  )
}
