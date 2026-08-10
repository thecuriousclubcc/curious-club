// The skin. Twelve token sets; one is active for three days at a time.
//
// The rule that makes the rotation survivable: none of this moves layout.
// Colour, type, shape, density, motion, texture and copy voice change. The
// position of every control stays exactly where muscle memory left it.

export type FontStack = 'serif' | 'sans' | 'mono' | 'rounded'

export type ThemeColors = {
  ground: string
  surface: string
  ink: string
  muted: string
  hairline: string
  accent: string
  accentInk: string
  ok: string
  caution: string
}

export type Theme = {
  id: string
  name: string
  nameJa: string
  colors: ThemeColors
  display: FontStack
  body: FontStack
  radius: number
  borderWidth: number
  shadow: 'none' | 'soft' | 'hard'
  density: 'comfortable' | 'compact'
  motion: 'still' | 'soft' | 'springy'
  texture: 'flat' | 'grain' | 'wash'
  /** Which pool the nudge and empty-state copy is drawn from. */
  voice: 'dry' | 'warm' | 'blunt' | 'silly'
}

// System stacks only. A theme font fetched from a CDN would break offline, and
// offline capture is the one thing this app cannot lose.
export const FONT_STACKS: Record<FontStack, string> = {
  serif:
    '"Iowan Old Style", Charter, "Bitstream Charter", Cambria, Georgia, "Hiragino Mincho ProN", "Yu Mincho", serif',
  sans: 'system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans JP", "Hiragino Kaku Gothic ProN", sans-serif',
  mono: 'ui-monospace, "Roboto Mono", "DejaVu Sans Mono", Menlo, Consolas, monospace',
  rounded:
    '"SF Pro Rounded", ui-rounded, "Varela Round", "Quicksand", system-ui, Roboto, "Noto Sans JP", sans-serif',
}

export const THEMES: Theme[] = [
  {
    id: 'ink-rice',
    name: 'Ink & Rice',
    nameJa: '墨と米',
    colors: {
      ground: '#EFEBE0',
      surface: '#F8F5EC',
      ink: '#1B1A17',
      muted: '#645F52',
      hairline: '#D6D0C0',
      accent: '#1F4E46',
      accentInk: '#F8F5EC',
      ok: '#2C6446',
      caution: '#7E5010',
    },
    display: 'serif',
    body: 'serif',
    radius: 2,
    borderWidth: 1,
    shadow: 'none',
    density: 'comfortable',
    motion: 'still',
    texture: 'flat',
    voice: 'dry',
  },
  {
    id: 'konbini-night',
    name: 'Konbini Night',
    nameJa: 'コンビニの夜',
    colors: {
      ground: '#101418',
      surface: '#171C21',
      ink: '#E8EEF2',
      muted: '#93A2AC',
      hairline: '#29323A',
      accent: '#3FE0D0',
      accentInk: '#06231F',
      ok: '#56D98A',
      caution: '#E0B457',
    },
    display: 'sans',
    body: 'sans',
    radius: 4,
    borderWidth: 1,
    shadow: 'soft',
    density: 'comfortable',
    motion: 'soft',
    texture: 'wash',
    voice: 'blunt',
  },
  {
    id: 'kraft',
    name: 'Kraft',
    nameJa: 'クラフト紙',
    colors: {
      ground: '#D9C7A9',
      surface: '#E9DEC7',
      ink: '#2A1C10',
      muted: '#634C2E',
      hairline: '#C2AB86',
      accent: '#54351E',
      accentInk: '#E9DEC7',
      ok: '#335C2F',
      caution: '#7A4A0C',
    },
    display: 'mono',
    body: 'serif',
    radius: 0,
    borderWidth: 1,
    shadow: 'hard',
    density: 'comfortable',
    motion: 'still',
    texture: 'grain',
    voice: 'warm',
  },
  {
    id: 'blueprint',
    name: 'Blueprint',
    nameJa: '青写真',
    colors: {
      ground: '#122E49',
      surface: '#173655',
      ink: '#E4EEF8',
      muted: '#A6C1DA',
      hairline: '#2C5480',
      accent: '#DCE9F5',
      accentInk: '#173655',
      ok: '#7FD6A8',
      caution: '#E8C070',
    },
    display: 'mono',
    body: 'sans',
    radius: 0,
    borderWidth: 1,
    shadow: 'none',
    density: 'compact',
    motion: 'still',
    texture: 'flat',
    voice: 'dry',
  },
  {
    id: 'terminal',
    name: 'Terminal',
    nameJa: '端末',
    colors: {
      ground: '#0A100C',
      surface: '#0F1712',
      ink: '#CFF7D8',
      muted: '#79B98B',
      hairline: '#1E3326',
      accent: '#5BE87A',
      accentInk: '#08150C',
      ok: '#5BE87A',
      caution: '#DCC45E',
    },
    display: 'mono',
    body: 'mono',
    radius: 0,
    borderWidth: 1,
    shadow: 'none',
    density: 'compact',
    motion: 'still',
    texture: 'flat',
    voice: 'blunt',
  },
  {
    id: 'sakura-dust',
    name: 'Sakura Dust',
    nameJa: '桜ぼこり',
    colors: {
      ground: '#F5E2E8',
      surface: '#FCF2F5',
      ink: '#2B1B21',
      muted: '#77555F',
      hairline: '#E6CBD5',
      accent: '#8E3355',
      accentInk: '#FCF2F5',
      ok: '#356344',
      caution: '#7E5010',
    },
    display: 'rounded',
    body: 'sans',
    radius: 14,
    borderWidth: 1,
    shadow: 'soft',
    density: 'comfortable',
    motion: 'springy',
    texture: 'wash',
    voice: 'warm',
  },
  {
    id: 'mikan',
    name: 'Mikan',
    nameJa: 'みかん',
    colors: {
      ground: '#FFEEDA',
      surface: '#FFF8EF',
      ink: '#2B1D0E',
      muted: '#6F5136',
      hairline: '#EAD6BC',
      accent: '#9C4A08',
      accentInk: '#FFF8EF',
      ok: '#33602F',
      caution: '#7A4A0C',
    },
    display: 'sans',
    body: 'sans',
    radius: 10,
    borderWidth: 1,
    shadow: 'soft',
    density: 'comfortable',
    motion: 'springy',
    texture: 'wash',
    voice: 'silly',
  },
  {
    id: 'deep-sea',
    name: 'Deep Sea',
    nameJa: '深海',
    colors: {
      ground: '#0D1E24',
      surface: '#12262E',
      ink: '#DCEDF0',
      muted: '#93B6BE',
      hairline: '#234049',
      accent: '#58C4D6',
      accentInk: '#06222A',
      ok: '#63CFA0',
      caution: '#DFB463',
    },
    display: 'serif',
    body: 'serif',
    radius: 6,
    borderWidth: 1,
    shadow: 'soft',
    density: 'comfortable',
    motion: 'soft',
    texture: 'wash',
    voice: 'dry',
  },
  {
    id: 'riso',
    name: 'Riso',
    nameJa: 'リソグラフ',
    colors: {
      ground: '#F1EFE4',
      surface: '#FBFAF3',
      ink: '#1B1B1B',
      muted: '#5C5C57',
      hairline: '#D9D7CA',
      accent: '#2540C4',
      accentInk: '#FBFAF3',
      ok: '#2A6E47',
      caution: '#7C5E08',
    },
    display: 'sans',
    body: 'sans',
    radius: 2,
    borderWidth: 2,
    shadow: 'hard',
    density: 'comfortable',
    motion: 'soft',
    texture: 'grain',
    voice: 'silly',
  },
  {
    id: 'concrete',
    name: 'Concrete',
    nameJa: 'コンクリート',
    colors: {
      ground: '#C4C4BF',
      surface: '#D6D6D1',
      ink: '#1C1C1A',
      muted: '#4B4B47',
      hairline: '#A6A6A0',
      accent: '#282826',
      accentInk: '#D6D6D1',
      ok: '#2A5F41',
      caution: '#6E4A0C',
    },
    display: 'mono',
    body: 'mono',
    radius: 0,
    borderWidth: 2,
    shadow: 'hard',
    density: 'compact',
    motion: 'still',
    texture: 'flat',
    voice: 'blunt',
  },
  {
    id: 'highlighter',
    name: 'Highlighter',
    nameJa: '蛍光ペン',
    colors: {
      ground: '#F5EEAE',
      surface: '#FCF8D6',
      ink: '#22220E',
      muted: '#605C1C',
      hairline: '#E0D888',
      accent: '#3F3F0A',
      accentInk: '#FCF8D6',
      ok: '#2A5F33',
      caution: '#6E4A0C',
    },
    display: 'sans',
    body: 'sans',
    radius: 2,
    borderWidth: 2,
    shadow: 'none',
    density: 'compact',
    motion: 'soft',
    texture: 'flat',
    voice: 'silly',
  },
  {
    id: 'midnight-mint',
    name: 'Midnight Mint',
    nameJa: '真夜中のミント',
    colors: {
      ground: '#14181A',
      surface: '#1B2124',
      ink: '#E2EFE8',
      muted: '#97B3A5',
      hairline: '#2B3A33',
      accent: '#8FE3B8',
      accentInk: '#0A241A',
      ok: '#8FE3B8',
      caution: '#D9B36A',
    },
    display: 'rounded',
    body: 'rounded',
    radius: 18,
    borderWidth: 1,
    shadow: 'soft',
    density: 'comfortable',
    motion: 'springy',
    texture: 'wash',
    voice: 'warm',
  },
]

const SHADOWS: Record<Theme['shadow'], string> = {
  none: 'none',
  soft: '0 1px 0 rgb(0 0 0 / 0.04), 0 10px 26px -20px rgb(0 0 0 / 0.5)',
  hard: '3px 3px 0 0 var(--hairline)',
}

const MOTION: Record<Theme['motion'], string> = {
  still: '0ms',
  soft: '160ms',
  springy: '260ms',
}

const DENSITY: Record<Theme['density'], { gutter: string; rowGap: string }> = {
  comfortable: { gutter: '1.15rem', rowGap: '0.85rem' },
  compact: { gutter: '0.8rem', rowGap: '0.55rem' },
}

/** The CSS custom properties for a theme, as a plain object. */
export function themeVars(theme: Theme): Record<string, string> {
  const d = DENSITY[theme.density]
  return {
    '--ground': theme.colors.ground,
    '--surface': theme.colors.surface,
    '--ink': theme.colors.ink,
    '--muted': theme.colors.muted,
    '--hairline': theme.colors.hairline,
    '--accent': theme.colors.accent,
    '--accent-ink': theme.colors.accentInk,
    '--ok': theme.colors.ok,
    '--caution': theme.colors.caution,
    '--font-display': FONT_STACKS[theme.display],
    '--font-body': FONT_STACKS[theme.body],
    '--radius': `${theme.radius}px`,
    '--radius-lg': `${Math.round(theme.radius * 1.6)}px`,
    '--border-width': `${theme.borderWidth}px`,
    '--shadow': SHADOWS[theme.shadow],
    '--gutter': d.gutter,
    '--row-gap': d.rowGap,
    '--motion': MOTION[theme.motion],
    '--texture': theme.texture,
  }
}
