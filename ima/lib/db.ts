import Dexie, { type Table } from 'dexie'
import { SNOOZE_LIMIT, SNOOZE_MS } from './tasks'

// Local-first. IndexedDB is the source of truth on the device, so the app opens
// and captures with no network — on a train, in a lift, in a basement. Sync to
// Postgres comes later and is never allowed to become a precondition for
// writing something down.

export type TaskState = 'inbox' | 'active' | 'parked' | 'done' | 'cold'
export type CognitiveLoad = 'light' | 'medium' | 'heavy'
export type TaskContext = 'work' | 'home' | 'errand' | 'phone' | 'computer'
export type SessionKind = 'dirty' | 'focus'

export interface Task {
  id?: number
  title: string
  /** A physical action, two minutes or less. Without one, NOW can't offer it. */
  firstStep?: string
  state: TaskState
  load?: CognitiveLoad
  context?: TaskContext
  estMinutes?: number
  actualMinutes?: number
  /** Epoch ms. Rare by design — only externally imposed dates go here. */
  hardDeadline?: number
  projectTag?: string
  snoozedUntil?: number
  snoozeCount: number
  createdAt: number
  updatedAt: number
  doneAt?: number
}

export interface Session {
  id?: number
  taskId: number
  kind: SessionKind
  startedAt: number
  endedAt?: number
}

export interface Reward {
  id?: number
  kind: string
  grantedAt: number
}

export interface Setting {
  key: string
  value: string
}

class ImaDb extends Dexie {
  tasks!: Table<Task, number>
  sessions!: Table<Session, number>
  rewards!: Table<Reward, number>
  settings!: Table<Setting, string>

  constructor() {
    super('ima')
    this.version(1).stores({
      tasks: '++id, state, createdAt, doneAt, hardDeadline, context, load',
      sessions: '++id, taskId, startedAt',
      rewards: '++id, grantedAt',
      settings: 'key',
    })
  }
}

export const db = new ImaDb()

const now = () => Date.now()

/**
 * Capture. The only required field is the text — every extra field is a reason
 * not to write it down at all.
 */
export async function capture(title: string): Promise<number | undefined> {
  const trimmed = title.trim()
  if (!trimmed) return undefined
  const t = now()
  return db.tasks.add({
    title: trimmed,
    state: 'inbox',
    snoozeCount: 0,
    createdAt: t,
    updatedAt: t,
  })
}

export async function setFirstStep(id: number, firstStep: string): Promise<void> {
  await db.tasks.update(id, {
    firstStep: firstStep.trim(),
    state: 'active',
    updatedAt: now(),
  })
}

/**
 * Accept an inbox item as real work. Deliberately does not ask for a first
 * step — NOW is the one place that prompt lives, so there's only ever one
 * screen to learn it on.
 */
export async function promote(id: number): Promise<void> {
  await db.tasks.update(id, { state: 'active', updatedAt: now() })
}

export async function triage(
  id: number,
  patch: Pick<Task, 'load' | 'context' | 'estMinutes' | 'hardDeadline' | 'projectTag'>,
): Promise<void> {
  await db.tasks.update(id, { ...patch, state: 'active', updatedAt: now() })
}

export async function complete(id: number): Promise<void> {
  const t = now()
  await db.tasks.update(id, { state: 'done', doneAt: t, updatedAt: t })
}

/**
 * "Not now" — never a failure state. After a few passes the task stops being
 * offered rather than nagging; ALL can hand it back later.
 */
export async function snooze(id: number): Promise<void> {
  const task = await db.tasks.get(id)
  if (!task) return
  const count = task.snoozeCount + 1
  await db.tasks.update(id, {
    snoozeCount: count,
    snoozedUntil: now() + SNOOZE_MS,
    state: count >= SNOOZE_LIMIT ? 'cold' : task.state,
    updatedAt: now(),
  })
}

export async function revive(id: number): Promise<void> {
  await db.tasks.update(id, {
    state: 'active',
    snoozeCount: 0,
    snoozedUntil: undefined,
    updatedAt: now(),
  })
}

export async function drop(id: number): Promise<void> {
  await db.tasks.delete(id)
}

/**
 * Amnesty. One tap, no confirmation, no count of what was dropped — a
 * confirmation dialog here would just be a second helping of shame.
 */
export async function amnesty(): Promise<void> {
  const ids = await db.tasks.where('state').equals('inbox').primaryKeys()
  await db.tasks.bulkDelete(ids)
}

export async function startSession(taskId: number, kind: SessionKind): Promise<number> {
  return db.sessions.add({ taskId, kind, startedAt: now() })
}

export async function endSession(id: number): Promise<void> {
  await db.sessions.update(id, { endedAt: now() })
}

export async function getSetting(key: string): Promise<string | undefined> {
  return (await db.settings.get(key))?.value
}

export async function setSetting(key: string, value: string): Promise<void> {
  await db.settings.put({ key, value })
}
