# いま / Ima

A personal task app for one Android phone, holding work and everyday things in
one flat list. Installable PWA, offline-first, free tier only.

The default screen shows exactly one task and nothing else. That is what the
name means.

## The one design principle

> **The skeleton never moves. The skin changes every 3 days.**

Muscle memory is the one executive-function freebie available: a button in the
same place becomes automatic, and automatic actions cost no activation energy.
So novelty goes into colour, type, texture, density, motion and copy voice — and
never into layout position.

Twelve themes, three days each, a 36-day cycle, derived from the date so it needs
no server state. The flip is at 4am so a theme never changes mid-session, and the
order reshuffles once per cycle so the sequence doesn't become predictable.

## Running it

```bash
npm install
npm run dev        # http://localhost:3000
npm run lint && npm test && npm run build   # the gate before committing
```

`npm run icons` regenerates the home-screen PNGs; `npm run build` does it for you.

## Putting it on the phone

Open the deployed URL in Chrome on Android, then **⋮ → Add to Home screen**.
After that:

- long-press the icon for **Quick capture**
- share text or a link from any app straight into the inbox
- it opens and captures with no network

Exclude the app from Android's battery optimisation, or scheduled nudges (a later
phase) will arrive late.

## What's here

- **NOW** — one task, full screen. Start dirty / Done / Not now / Nope
- **IN** — capture and inbox. The only required field is the text
- **DAY** — hard deadlines and what got finished today
- **ALL** — the full list, behind a deliberate tap. Browse mode rotates with the skin
- **ME** — the rolling 7-day count, the done log, theme pin/shuffle, language

Data lives in IndexedDB via Dexie. Nothing leaves the device yet.

## What is deliberately absent

Each of these is a known failure mode, not an oversight:

- **priority levels** — ranking is the paralysis, not the cure
- **streaks that reset to zero** — turns one bad day into quitting
- **red badges and overdue counts** — no theme contains a saturated red, and a test enforces it
- **nested projects and folders** — organising becomes the procrastination
- **required fields in capture** — every field is a reason not to write it down

`ME` stays thin on purpose. The theme changes by itself; letting you choose one
would make tending the app a way of avoiding the work.

## Conventions

- UI copy is bilingual (JA/EN) from `lib/i18n.ts`; code and comments in English
- Every visual value is a CSS custom property set by the active theme. Components
  never name a colour
- `lib/rotation.ts`, `lib/tasks.ts` and `lib/contrast.ts` are pure and covered by
  `tests/`. Theme legibility floors are enforced there, not by eye
- No paid services. Ever

## Next

Time cushion and analog timers, routines, basics tracking, energy matching,
AI task splitting, then web push via Supabase `pg_cron`. Full plan:
`docs/adhd-task-app-plan.md` in the `curious-club` repo.
