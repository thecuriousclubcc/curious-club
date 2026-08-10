# CLAUDE.md — ima

Personal ADHD task app (PWA) for one Android phone. Single user, local-first.

## Hard constraints
- **Free tier only.** No paid APIs, plans, or infra. Vercel free, Supabase free, Groq free tier.
- UI copy is bilingual JA/EN via `lib/i18n.ts`. Code and comments in English.
- **Offline capture must never break.** IndexedDB is the source of truth; a network
  failure, a storage exception, or a missing API may degrade features but must not
  stop a thought being written down.

## The design rule that overrides convenience
The skeleton never moves; the skin changes every 3 days. Novelty belongs in colour,
type, shape, density, motion, texture and copy voice. **Never in layout position** —
tab order and the NOW screen's structure are fixed forever. `ALL` may rotate its
browse mode; `NOW` may not.

## Deliberately absent — do not add
- priority fields or any ranking UI
- streaks that can reset to zero
- red status colour, overdue counts, guilt counters
- nested projects, folders, hierarchies
- required fields in capture
- settings knobs beyond pin / shuffle / language

These are failure modes, not gaps. If a task seems to need one, say so rather than
adding it quietly.

## Stack
- Next.js 16 App Router + TypeScript + Tailwind v3, deployed on Vercel.
- Dexie (IndexedDB) for all data — see `lib/db.ts`.
- Themes are CSS custom properties only. Components must never name a colour;
  use the Tailwind tokens (`bg-surface`, `text-muted`, `border-hairline`, …).

## Commands
- `npm run dev` / `npm run build` / `npm run lint`
- `npm test` — node test runner via tsx over `tests/*.test.ts`
- `npm run icons` — regenerates home-screen PNGs (runs as part of `build`)

## Layout
- `app/` — `/` (the whole app, client-side tabs) and `/capture` (share target + shortcut)
- `components/` — one file per screen, plus `TabBar`, `CaptureBar`, `Timer`, `ui.ts` class strings
- `lib/` — `themes.ts` (token sets), `rotation.ts` (3-day maths), `tasks.ts` (selection),
  `contrast.ts`, `db.ts`, `i18n.ts`, `prefs.ts`, `bootstrap.ts` (pre-paint theme script)
- `tests/` — pure logic and theme legibility floors

## Conventions
- Keep `lib/rotation.ts`, `lib/tasks.ts`, `lib/contrast.ts` pure and dependency-free
  so they stay testable without a browser.
- `lib/bootstrap.ts` duplicates the rotation maths as an inline script string to avoid
  a first-paint flash. If you change rotation, change both.
- Run `npm run lint && npm test && npm run build` before committing; there is no CI yet.
