'use client'

import { useCallback, useEffect, useState } from 'react'
import { useLiveQuery } from 'dexie-react-hooks'
import { db, drop, type Task } from '@/lib/db'
import { t } from '@/lib/i18n'
import { AllScreen } from './AllScreen'
import { DayScreen } from './DayScreen'
import { InScreen } from './InScreen'
import { MeScreen } from './MeScreen'
import { NowScreen } from './NowScreen'
import { TabBar, type Tab } from './TabBar'
import { useSettings } from './useSettings'
import { btn } from './ui'

export function AppShell() {
  const { locale, changeLocale, rotation, pinned, togglePin, shuffleNow, showReveal } =
    useSettings()
  const [tab, setTab] = useState<Tab>('now')
  const [undoable, setUndoable] = useState<Task | null>(null)

  const tasks = useLiveQuery(() => db.tasks.toArray(), [], [] as Task[])

  useEffect(() => {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(() => {
        // Offline support is a bonus layer; failing to register must not
        // stop the app from working.
      })
    }
  }, [])

  /**
   * "Nope" deletes immediately and offers an undo, rather than asking "are you
   * sure?" — a confirmation dialog on a task you have decided against is just
   * one more thing to feel bad about.
   */
  const handleDrop = useCallback(async (task: Task) => {
    if (task.id === undefined) return
    await drop(task.id)
    setUndoable(task)
  }, [])

  useEffect(() => {
    if (!undoable) return
    const id = window.setTimeout(() => setUndoable(null), 7000)
    return () => window.clearTimeout(id)
  }, [undoable])

  const shared = { tasks, locale, theme: rotation.theme, slot: rotation.slot }

  return (
    <main className="relative z-[1] mx-auto max-w-xl">
      {showReveal ? (
        <div className="reveal flex items-baseline justify-center gap-2 border-b-token border-hairline bg-surface px-gutter py-2">
          <span className="font-display text-[0.68rem] uppercase tracking-[0.14em] text-muted">
            {t(locale, 'reveal.new')}
          </span>
          <span className="font-display text-sm text-accent">
            {locale === 'ja' ? rotation.theme.nameJa : rotation.theme.name}
          </span>
        </div>
      ) : null}

      {tab === 'now' ? <NowScreen {...shared} onDrop={handleDrop} /> : null}
      {tab === 'in' ? <InScreen {...shared} onDrop={handleDrop} /> : null}
      {tab === 'day' ? <DayScreen tasks={tasks} locale={locale} /> : null}
      {tab === 'all' ? <AllScreen {...shared} /> : null}
      {tab === 'me' ? (
        <MeScreen
          tasks={tasks}
          locale={locale}
          onLocale={changeLocale}
          rotation={rotation}
          pinned={pinned}
          onTogglePin={togglePin}
          onShuffle={shuffleNow}
        />
      ) : null}

      {undoable ? (
        <div className="fixed inset-x-0 bottom-20 z-20 mx-auto flex max-w-xl items-center justify-between gap-3 border-token border-hairline bg-surface px-4 py-3 shadow-token">
          <span className="truncate text-sm text-muted">{undoable.title}</span>
          <button
            type="button"
            className={btn}
            onClick={async () => {
              await db.tasks.add(undoable)
              setUndoable(null)
            }}
          >
            {locale === 'ja' ? '戻す' : 'Undo'}
          </button>
        </div>
      ) : null}

      <TabBar active={tab} onChange={setTab} locale={locale} />
    </main>
  )
}
