import { THEMES, type Theme } from './themes'

// Rotation is derived from the date, so it needs no server state and lands on
// the same theme on every device. Two details that matter more than they look:
//
//  - the flip is at 4am, not midnight, so a theme never changes mid-session
//  - the order reshuffles once per full cycle, so the sequence itself doesn't
//    become predictable after the first pass

export const PERIOD_DAYS = 3
export const FLIP_HOUR = 4
export const DAY_MS = 86_400_000

/** Calendar day number in local time, with the day boundary moved to 4am. */
export function localDayNumber(d: Date): number {
  const shifted = new Date(d.getTime() - FLIP_HOUR * 60 * 60 * 1000)
  return Math.floor((shifted.getTime() - shifted.getTimezoneOffset() * 60_000) / DAY_MS)
}

/** Anchor day. Noon keeps the 4am shift away from a day boundary. */
export const EPOCH_DAY = localDayNumber(new Date(2026, 0, 1, 12, 0, 0))

/** Deterministic Fisher–Yates, so a given cycle always shuffles the same way. */
export function seededShuffle(n: number, seed: number): number[] {
  const a = Array.from({ length: n }, (_, i) => i)
  // Math.imul keeps the multiply in int32. Plain `*` would exceed 2^53 and
  // silently lose precision — still deterministic, but no longer an LCG.
  let s = (Math.imul(seed, 2654435761) + 1) & 0x7fffffff
  for (let i = n - 1; i > 0; i--) {
    s = (Math.imul(s, 1103515245) + 12345) & 0x7fffffff
    const j = s % (i + 1)
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

export function themeSlot(now: Date, shuffleOffset = 0): number {
  return Math.floor((localDayNumber(now) - EPOCH_DAY) / PERIOD_DAYS) + shuffleOffset
}

export function themeIndexForSlot(slot: number): number {
  const cycle = Math.floor(slot / THEMES.length)
  const order = seededShuffle(THEMES.length, cycle)
  const i = ((slot % THEMES.length) + THEMES.length) % THEMES.length
  return order[i]
}

export function themeForSlot(slot: number): Theme {
  return THEMES[themeIndexForSlot(slot)]
}

/** Whole days remaining before the current theme gives way to the next. */
export function daysLeftInSlot(now: Date): number {
  const elapsed = (localDayNumber(now) - EPOCH_DAY) % PERIOD_DAYS
  const into = ((elapsed % PERIOD_DAYS) + PERIOD_DAYS) % PERIOD_DAYS
  return PERIOD_DAYS - into
}

/** The exact instant the next theme takes over. */
export function nextFlipAt(now: Date): Date {
  const flip = new Date(now)
  flip.setHours(FLIP_HOUR, 0, 0, 0)
  if (flip.getTime() <= now.getTime()) flip.setDate(flip.getDate() + 1)
  const extra = daysLeftInSlot(now) - 1
  flip.setDate(flip.getDate() + extra)
  return flip
}

export type Rotation = {
  theme: Theme
  slot: number
  cycle: number
  pinned: boolean
  daysLeft: number
}

/**
 * The theme in force right now. `pinnedId` freezes rotation; `shuffleOffset`
 * is bumped by "shuffle now" for when today's theme simply grates.
 */
export function resolveRotation(
  now: Date,
  opts: { pinnedId?: string | null; shuffleOffset?: number } = {},
): Rotation {
  const slot = themeSlot(now, opts.shuffleOffset ?? 0)
  const pinned = THEMES.find((t) => t.id === opts.pinnedId)
  return {
    theme: pinned ?? themeForSlot(slot),
    slot,
    cycle: Math.floor(slot / THEMES.length) + 1,
    pinned: Boolean(pinned),
    daysLeft: daysLeftInSlot(now),
  }
}
