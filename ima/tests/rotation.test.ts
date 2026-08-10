import test from 'node:test'
import assert from 'node:assert/strict'
import { THEMES } from '../lib/themes'
import {
  PERIOD_DAYS,
  daysLeftInSlot,
  localDayNumber,
  nextFlipAt,
  resolveRotation,
  seededShuffle,
  themeForSlot,
  themeSlot,
} from '../lib/rotation'

const at = (y: number, m: number, d: number, h = 12, min = 0) => new Date(y, m - 1, d, h, min)

test('a theme holds for exactly three days', () => {
  const start = at(2026, 3, 2)
  const first = themeSlot(start)
  assert.equal(themeSlot(at(2026, 3, 3)), first)
  assert.equal(themeSlot(at(2026, 3, 4)), first)
  assert.notEqual(themeSlot(at(2026, 3, 5)), first)
  assert.equal(themeSlot(at(2026, 3, 5)), first + 1)
})

test('the flip is at 4am, so a late-night session keeps its theme', () => {
  // 01:30 still belongs to the previous day; 04:30 is the new one.
  const lateNight = at(2026, 3, 5, 1, 30)
  const evening = at(2026, 3, 4, 23, 0)
  assert.equal(themeSlot(lateNight), themeSlot(evening))

  const morning = at(2026, 3, 5, 4, 30)
  assert.equal(localDayNumber(morning), localDayNumber(evening) + 1)
})

test('nextFlipAt lands on a 4am boundary in the future', () => {
  const now = at(2026, 3, 3, 21, 15)
  const flip = nextFlipAt(now)
  assert.ok(flip.getTime() > now.getTime())
  assert.equal(flip.getHours(), 4)
  assert.equal(flip.getMinutes(), 0)
  // Never further out than the period itself.
  assert.ok(flip.getTime() - now.getTime() <= PERIOD_DAYS * 24 * 60 * 60 * 1000)
})

test('daysLeftInSlot counts down 3, 2, 1 and never reaches zero', () => {
  const seen = [at(2026, 3, 2), at(2026, 3, 3), at(2026, 3, 4)].map(daysLeftInSlot)
  assert.deepEqual(seen, [3, 2, 1])
  for (let d = 1; d <= 60; d++) {
    const left = daysLeftInSlot(at(2026, 4, d))
    assert.ok(left >= 1 && left <= PERIOD_DAYS, `day ${d} gave ${left}`)
  }
})

test('a full cycle visits every theme exactly once', () => {
  const seen = new Set<string>()
  for (let slot = 0; slot < THEMES.length; slot++) seen.add(themeForSlot(slot).id)
  assert.equal(seen.size, THEMES.length)
})

test('the next cycle comes in a different order', () => {
  const first = Array.from({ length: THEMES.length }, (_, i) => themeForSlot(i).id)
  const second = Array.from({ length: THEMES.length }, (_, i) =>
    themeForSlot(i + THEMES.length).id,
  )
  assert.notDeepEqual(first, second)
  assert.deepEqual([...second].sort(), [...first].sort())
})

test('negative slots resolve instead of throwing', () => {
  for (let slot = -30; slot < 0; slot++) {
    assert.ok(themeForSlot(slot).id)
  }
})

test('seededShuffle is deterministic and total', () => {
  assert.deepEqual(seededShuffle(12, 7), seededShuffle(12, 7))
  assert.deepEqual([...seededShuffle(12, 7)].sort((a, b) => a - b), [
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11,
  ])
})

test('pinning freezes the theme across a flip', () => {
  const pinnedId = THEMES[4].id
  const before = resolveRotation(at(2026, 3, 2), { pinnedId })
  const after = resolveRotation(at(2026, 5, 20), { pinnedId })
  assert.equal(before.theme.id, pinnedId)
  assert.equal(after.theme.id, pinnedId)
  assert.ok(before.pinned)
})

test('shuffle now advances to a different theme', () => {
  const day = at(2026, 3, 2)
  const before = resolveRotation(day)
  const after = resolveRotation(day, { shuffleOffset: 1 })
  assert.notEqual(before.theme.id, after.theme.id)
  assert.equal(after.slot, before.slot + 1)
})

test('an unknown pinned id falls back to the rotation', () => {
  const day = at(2026, 3, 2)
  const r = resolveRotation(day, { pinnedId: 'deleted-theme' })
  assert.equal(r.theme.id, resolveRotation(day).theme.id)
  assert.ok(!r.pinned)
})
