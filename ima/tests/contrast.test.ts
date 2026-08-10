import test from 'node:test'
import assert from 'node:assert/strict'
import { THEMES, themeVars, type ThemeColors } from '../lib/themes'
import { contrastRatio, hexToRgb } from '../lib/contrast'

// A theme system with no legibility floor eventually ships a day the app can't
// be read on. On a phone that day is the day the app gets deleted, so the floor
// is a test rather than a guideline.

const TOKENS: (keyof ThemeColors)[] = [
  'ground',
  'surface',
  'ink',
  'muted',
  'hairline',
  'accent',
  'accentInk',
  'ok',
  'caution',
]

test('every theme defines every colour token as a 6-digit hex', () => {
  for (const theme of THEMES) {
    for (const token of TOKENS) {
      const value = theme.colors[token]
      assert.ok(value, `${theme.id} is missing ${token}`)
      assert.match(value, /^#[0-9a-fA-F]{6}$/, `${theme.id}.${token} = ${value}`)
    }
  }
})

test('theme ids are unique', () => {
  const ids = THEMES.map((t) => t.id)
  assert.equal(new Set(ids).size, ids.length)
})

test('body text clears AAA on both surface and ground', () => {
  for (const theme of THEMES) {
    for (const bg of ['surface', 'ground'] as const) {
      const ratio = contrastRatio(theme.colors.ink, theme.colors[bg])
      assert.ok(ratio >= 7, `${theme.id}: ink on ${bg} is ${ratio.toFixed(2)}:1, needs 7`)
    }
  }
})

test('secondary text clears AA on both surface and ground', () => {
  for (const theme of THEMES) {
    for (const bg of ['surface', 'ground'] as const) {
      const ratio = contrastRatio(theme.colors.muted, theme.colors[bg])
      assert.ok(ratio >= 4.5, `${theme.id}: muted on ${bg} is ${ratio.toFixed(2)}:1, needs 4.5`)
    }
  }
})

test('text on an accent fill clears AA', () => {
  for (const theme of THEMES) {
    const ratio = contrastRatio(theme.colors.accentInk, theme.colors.accent)
    assert.ok(ratio >= 4.5, `${theme.id}: accentInk on accent is ${ratio.toFixed(2)}:1`)
  }
})

test('accent is distinguishable as a UI element on both backgrounds', () => {
  for (const theme of THEMES) {
    for (const bg of ['surface', 'ground'] as const) {
      const ratio = contrastRatio(theme.colors.accent, theme.colors[bg])
      assert.ok(ratio >= 3, `${theme.id}: accent on ${bg} is ${ratio.toFixed(2)}:1, needs 3`)
    }
  }
})

test('status colours stay readable as text', () => {
  for (const theme of THEMES) {
    for (const token of ['ok', 'caution'] as const) {
      const ratio = contrastRatio(theme.colors[token], theme.colors.surface)
      assert.ok(ratio >= 4.5, `${theme.id}: ${token} on surface is ${ratio.toFixed(2)}:1`)
    }
  }
})

test('hairlines are visible without being borders in disguise', () => {
  for (const theme of THEMES) {
    const ratio = contrastRatio(theme.colors.hairline, theme.colors.surface)
    assert.ok(ratio >= 1.25, `${theme.id}: hairline on surface is ${ratio.toFixed(2)}:1`)
  }
})

test('no theme uses red for anything', () => {
  // Overdue red is the most reliable way to make a task list unfaceable, so the
  // palette simply does not contain it. Judged on hue, not on channel gaps —
  // burnt orange (~27°) is a legitimate accent and must survive this.
  for (const theme of THEMES) {
    for (const token of TOKENS) {
      const hex = theme.colors[token]
      const [r, g, b] = hexToRgb(hex).map((v) => v / 255)
      const max = Math.max(r, g, b)
      const min = Math.min(r, g, b)
      const delta = max - min
      // Chroma, not HSL saturation: saturation inflates at extreme lightness,
      // which would flag a pale pink wash as an alarm. Only a genuinely vivid
      // colour can read as "you have failed".
      if (delta < 0.3) continue

      let hue = 0
      if (max === r) hue = 60 * (((g - b) / delta + 6) % 6)
      else if (max === g) hue = 60 * ((b - r) / delta + 2)
      else hue = 60 * ((r - g) / delta + 4)

      const isRed = hue < 20 || hue > 340
      assert.ok(
        !isRed,
        `${theme.id}.${token} = ${hex} is hue ${hue.toFixed(0)}° at chroma ${delta.toFixed(2)}, which reads as red`,
      )
    }
  }
})

test('themeVars emits a complete custom-property set', () => {
  for (const theme of THEMES) {
    const vars = themeVars(theme)
    for (const key of [
      '--ground',
      '--surface',
      '--ink',
      '--muted',
      '--hairline',
      '--accent',
      '--accent-ink',
      '--ok',
      '--caution',
      '--font-display',
      '--font-body',
      '--radius',
      '--border-width',
      '--shadow',
      '--gutter',
      '--motion',
    ]) {
      assert.ok(vars[key], `${theme.id} produced no ${key}`)
    }
  }
})
