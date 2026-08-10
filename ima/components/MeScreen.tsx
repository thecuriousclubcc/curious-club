'use client'

import type { Task } from '@/lib/db'
import { rollingDone } from '@/lib/tasks'
import { LOCALES, t, tf, type Locale } from '@/lib/i18n'
import type { Rotation } from '@/lib/rotation'
import { btn, btnQuiet, card, label, screen } from './ui'

/**
 * Deliberately thin. The real risk with a task app is that tending it replaces
 * doing the work, so there are no knobs here beyond pin, shuffle and language —
 * and no way to reorganise anything into folders.
 */
export function MeScreen({
  tasks,
  locale,
  onLocale,
  rotation,
  pinned,
  onTogglePin,
  onShuffle,
}: {
  tasks: Task[]
  locale: Locale
  onLocale: (locale: Locale) => void
  rotation: Rotation
  pinned: boolean
  onTogglePin: () => void
  onShuffle: () => void
}) {
  const now = new Date()
  const count = rollingDone(tasks, now)
  const log = tasks
    .filter((task) => task.doneAt !== undefined)
    .sort((a, b) => (b.doneAt ?? 0) - (a.doneAt ?? 0))
    .slice(0, 20)
  const tag = locale === 'ja' ? 'ja-JP' : 'en-GB'

  return (
    <div className={screen}>
      {/* Evidence against "I did nothing", which is the more damaging lie. */}
      <div className={`${card} flex flex-col gap-1 p-4`}>
        <p className={label}>{t(locale, 'me.streak')}</p>
        <p className="font-display text-4xl tabular-nums text-ink">{count}</p>
        <p className="text-xs text-muted">{t(locale, 'me.streakNote')}</p>
      </div>

      <div className={`${card} flex flex-col gap-2 p-4`}>
        <p className={label}>{t(locale, 'me.theme')}</p>
        <p className="font-display text-lg text-ink">
          {locale === 'ja' ? rotation.theme.nameJa : rotation.theme.name}
        </p>
        <p className="text-xs text-muted">
          {pinned
            ? t(locale, 'me.themePinned')
            : tf(locale, rotation.daysLeft === 1 ? 'me.dayLeft' : 'me.daysLeft', {
                n: rotation.daysLeft,
              })}
        </p>
        <div className="mt-1 flex flex-wrap gap-2">
          <button type="button" className={btn} onClick={onTogglePin}>
            {t(locale, pinned ? 'me.unpin' : 'me.pin')}
          </button>
          <button type="button" className={btn} onClick={onShuffle}>
            {t(locale, 'me.shuffle')}
          </button>
        </div>
        <p className="text-xs text-muted">{t(locale, 'me.rotationNote')}</p>
      </div>

      <div className={`${card} flex flex-col gap-2 p-4`}>
        <p className={label}>{t(locale, 'me.language')}</p>
        <div className="flex gap-2">
          {LOCALES.map((option) => (
            <button
              key={option}
              type="button"
              className={btn}
              aria-pressed={option === locale}
              style={option === locale ? { borderColor: 'var(--accent)' } : undefined}
              onClick={() => onLocale(option)}
            >
              {option === 'ja' ? '日本語' : 'English'}
            </button>
          ))}
        </div>
      </div>

      <p className={`${label} mt-4`}>{t(locale, 'me.log')}</p>
      {log.length === 0 ? (
        <p className="text-sm text-muted">{t(locale, 'empty.log')}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {log.map((task) => (
            <li key={task.id} className="flex items-baseline gap-3">
              <span className="font-display text-xs tabular-nums text-muted">
                {new Date(task.doneAt ?? 0).toLocaleDateString(tag, {
                  month: 'numeric',
                  day: 'numeric',
                })}
              </span>
              <span className="text-base text-muted">{task.title}</span>
            </li>
          ))}
        </ul>
      )}

      <p className={`${btnQuiet} mt-6 text-center text-xs`}>{t(locale, 'me.install')}</p>
    </div>
  )
}
