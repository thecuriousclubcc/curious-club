import test from 'node:test'
import assert from 'node:assert/strict'
import type { Task } from '../lib/db'
import {
  SNOOZE_LIMIT,
  browseModeForSlot,
  doneOn,
  isSnoozed,
  needsFirstStep,
  pickNow,
  rollingDone,
  upcomingDeadlines,
} from '../lib/tasks'

const NOW = new Date(2026, 5, 10, 10, 0)
const ms = (h: number) => h * 60 * 60 * 1000

let seq = 0
function task(over: Partial<Task> = {}): Task {
  seq += 1
  return {
    id: seq,
    title: `task ${seq}`,
    state: 'active',
    snoozeCount: 0,
    createdAt: NOW.getTime() - ms(24),
    updatedAt: NOW.getTime() - ms(24),
    ...over,
  }
}

test('NOW offers exactly one task, or nothing', () => {
  assert.equal(pickNow([], NOW), undefined)
  const only = task()
  assert.equal(pickNow([only], NOW)?.id, only.id)
})

test('a deadline inside 48h jumps the queue', () => {
  const old = task({ createdAt: NOW.getTime() - ms(500) })
  const urgent = task({ hardDeadline: NOW.getTime() + ms(6) })
  assert.equal(pickNow([old, urgent], NOW)?.id, urgent.id)
})

test('a distant deadline does not jump the queue', () => {
  const old = task({ createdAt: NOW.getTime() - ms(500) })
  const later = task({ hardDeadline: NOW.getTime() + ms(24 * 30) })
  assert.equal(pickNow([old, later], NOW)?.id, old.id)
})

test('the nearest of two urgent deadlines wins', () => {
  const soon = task({ hardDeadline: NOW.getTime() + ms(2) })
  const sooner = task({ hardDeadline: NOW.getTime() + ms(1) })
  assert.equal(pickNow([soon, sooner], NOW)?.id, sooner.id)
})

test('triaged work beats an untouched inbox item', () => {
  const inbox = task({ state: 'inbox', createdAt: NOW.getTime() - ms(900) })
  const active = task({ state: 'active' })
  assert.equal(pickNow([inbox, active], NOW)?.id, active.id)
})

test('done, parked and cold tasks are never offered', () => {
  for (const state of ['done', 'parked', 'cold'] as const) {
    assert.equal(pickNow([task({ state })], NOW), undefined)
  }
})

test('a snoozed task is skipped until its snooze expires', () => {
  const snoozed = task({ snoozedUntil: NOW.getTime() + ms(0.25) })
  assert.ok(isSnoozed(snoozed, NOW))
  assert.equal(pickNow([snoozed], NOW), undefined)

  const later = new Date(NOW.getTime() + ms(1))
  assert.ok(!isSnoozed(snoozed, later))
  assert.equal(pickNow([snoozed], later)?.id, snoozed.id)
})

test('a repeatedly deferred task sinks below a fresh one', () => {
  const deferred = task({ snoozeCount: SNOOZE_LIMIT - 1, createdAt: NOW.getTime() - ms(900) })
  const fresh = task()
  assert.equal(pickNow([deferred, fresh], NOW)?.id, fresh.id)
})

test('selection is stable for the same input', () => {
  const pool = [task(), task(), task({ state: 'inbox' })]
  const first = pickNow(pool, NOW)?.id
  assert.equal(pickNow([...pool].reverse(), NOW)?.id, first)
})

test('the 7-day count ignores a gap instead of resetting', () => {
  const tasks = [
    task({ state: 'done', doneAt: NOW.getTime() - ms(1) }),
    task({ state: 'done', doneAt: NOW.getTime() - ms(24 * 4) }),
    // Nothing at all on days 2 and 3 — the count must survive that.
    task({ state: 'done', doneAt: NOW.getTime() - ms(24 * 6) }),
    task({ state: 'done', doneAt: NOW.getTime() - ms(24 * 9) }), // outside the window
  ]
  assert.equal(rollingDone(tasks, NOW), 3)
})

test('the 7-day count is never negative and never throws on an empty history', () => {
  assert.equal(rollingDone([], NOW), 0)
})

test('doneOn returns only that calendar day, newest first', () => {
  const early = task({ state: 'done', doneAt: new Date(2026, 5, 10, 8, 0).getTime() })
  const late = task({ state: 'done', doneAt: new Date(2026, 5, 10, 9, 30).getTime() })
  const yesterday = task({ state: 'done', doneAt: new Date(2026, 5, 9, 9, 30).getTime() })
  const got = doneOn([early, late, yesterday], NOW).map((t) => t.id)
  assert.deepEqual(got, [late.id, early.id])
})

test('upcomingDeadlines lists only unfinished hard deadlines in order', () => {
  const soon = task({ hardDeadline: NOW.getTime() + ms(20) })
  const later = task({ hardDeadline: NOW.getTime() + ms(100) })
  const finished = task({ state: 'done', hardDeadline: NOW.getTime() + ms(30) })
  const soft = task()
  const got = upcomingDeadlines([later, soon, finished, soft], NOW).map((t) => t.id)
  assert.deepEqual(got, [soon.id, later.id])
})

test('a task with no first step is flagged for one', () => {
  assert.ok(needsFirstStep(task()))
  assert.ok(needsFirstStep(task({ firstStep: '   ' })))
  assert.ok(!needsFirstStep(task({ firstStep: 'open the editor' })))
})

test('browse mode rotates with the slot and always resolves', () => {
  const modes = [0, 1, 2, 3].map(browseModeForSlot)
  assert.deepEqual(modes, ['list', 'deck', 'roulette', 'list'])
  assert.ok(browseModeForSlot(-1))
})
