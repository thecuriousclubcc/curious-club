import type { Task } from './db'

// Selection logic lives here as pure functions over plain arrays, so it can be
// tested without a browser or IndexedDB. Note what is missing: there is no
// priority field and nothing reads one. Ranking is the paralysis, not the cure.

/** Deadlines this close are the only thing allowed to jump the queue. */
export const DEADLINE_HORIZON_MS = 48 * 60 * 60 * 1000

/** After this many "not now"s a task stops being offered and goes quiet. */
export const SNOOZE_LIMIT = 3

export const SNOOZE_MS = 30 * 60 * 1000

export function isSnoozed(task: Task, now: Date): boolean {
  return task.snoozedUntil !== undefined && task.snoozedUntil > now.getTime()
}

export function isUrgent(task: Task, now: Date): boolean {
  return (
    task.hardDeadline !== undefined &&
    task.hardDeadline - now.getTime() <= DEADLINE_HORIZON_MS
  )
}

/**
 * The single task NOW offers. Deterministic, and deliberately not a ranking
 * the user has to agree with — it just has to be defensible and stable.
 */
export function pickNow(tasks: Task[], now: Date): Task | undefined {
  const eligible = tasks.filter(
    (t) => (t.state === 'active' || t.state === 'inbox') && !isSnoozed(t, now),
  )

  const scored = eligible.slice().sort((a, b) => {
    const ua = isUrgent(a, now)
    const ub = isUrgent(b, now)
    if (ua !== ub) return ua ? -1 : 1
    if (ua && ub) return (a.hardDeadline ?? 0) - (b.hardDeadline ?? 0)

    // Already-triaged work beats an untouched inbox item.
    const sa = a.state === 'active' ? 0 : 1
    const sb = b.state === 'active' ? 0 : 1
    if (sa !== sb) return sa - sb

    if (a.snoozeCount !== b.snoozeCount) return a.snoozeCount - b.snoozeCount
    if (a.createdAt !== b.createdAt) return a.createdAt - b.createdAt
    // Total order, so two tasks captured in the same millisecond can't make
    // NOW offer a different one each time it renders.
    return (a.id ?? 0) - (b.id ?? 0)
  })

  return scored[0]
}

/**
 * A count, never a streak that can break. Seven rolling days, so one bad day
 * lowers the number instead of zeroing it — a reset turns a bad day into
 * quitting the app entirely.
 */
export function rollingDone(tasks: Task[], now: Date, days = 7): number {
  const since = now.getTime() - days * 24 * 60 * 60 * 1000
  return tasks.filter((t) => t.doneAt !== undefined && t.doneAt >= since).length
}

export function doneOn(tasks: Task[], day: Date): Task[] {
  const start = new Date(day)
  start.setHours(0, 0, 0, 0)
  const end = start.getTime() + 24 * 60 * 60 * 1000
  return tasks
    .filter((t) => t.doneAt !== undefined && t.doneAt >= start.getTime() && t.doneAt < end)
    .sort((a, b) => (b.doneAt ?? 0) - (a.doneAt ?? 0))
}

/** Hard deadlines only — the whole point is that they stay legible. */
export function upcomingDeadlines(tasks: Task[], now: Date, withinDays = 7): Task[] {
  const limit = now.getTime() + withinDays * 24 * 60 * 60 * 1000
  return tasks
    .filter(
      (t) =>
        t.state !== 'done' &&
        t.hardDeadline !== undefined &&
        t.hardDeadline <= limit,
    )
    .sort((a, b) => (a.hardDeadline ?? 0) - (b.hardDeadline ?? 0))
}

/** A first step has to be something a body can do, so it must be short. */
export function needsFirstStep(task: Task): boolean {
  return !task.firstStep || task.firstStep.trim().length === 0
}

/** Which browse mode ALL uses. Skin-only novelty goes stale; this rotates too. */
export const BROWSE_MODES = ['list', 'deck', 'roulette'] as const
export type BrowseMode = (typeof BROWSE_MODES)[number]

export function browseModeForSlot(slot: number): BrowseMode {
  const i = ((slot % BROWSE_MODES.length) + BROWSE_MODES.length) % BROWSE_MODES.length
  return BROWSE_MODES[i]
}
