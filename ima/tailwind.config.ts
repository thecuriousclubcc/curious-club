import type { Config } from 'tailwindcss'

// Every visual value resolves to a CSS custom property. The active theme sets
// those properties on <html>, so components are written once and never
// per-theme. See lib/themes.ts for the token sets and lib/rotation.ts for
// which one is active today.
const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ground: 'var(--ground)',
        surface: 'var(--surface)',
        ink: 'var(--ink)',
        muted: 'var(--muted)',
        hairline: 'var(--hairline)',
        accent: 'var(--accent)',
        'accent-ink': 'var(--accent-ink)',
        ok: 'var(--ok)',
        caution: 'var(--caution)',
      },
      fontFamily: {
        display: 'var(--font-display)',
        body: 'var(--font-body)',
      },
      borderRadius: {
        token: 'var(--radius)',
        'token-lg': 'var(--radius-lg)',
      },
      borderWidth: {
        token: 'var(--border-width)',
      },
      boxShadow: {
        token: 'var(--shadow)',
      },
      spacing: {
        gutter: 'var(--gutter)',
        row: 'var(--row-gap)',
      },
      transitionDuration: {
        token: 'var(--motion)',
      },
      minHeight: {
        // Android touch target floor, enforced in tests/contrast.test.ts.
        tap: '48px',
      },
      minWidth: {
        tap: '48px',
      },
    },
  },
  plugins: [],
}

export default config
