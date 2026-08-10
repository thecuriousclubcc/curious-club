# いま / Ima — build plan

A personal task app for one Android phone. Working name **いま (Ima)** — "now" — because the
default screen shows exactly one thing and nothing else. Rename freely.

This document is the spec. The app itself ships from a **separate repo and separate Vercel
project**; this file lives here only because that's where the planning happened.

## Framing

The goal isn't to make an ADHD brain work like a neurotypical one. It's to move the
executive-function labour — remembering, sequencing, estimating, initiating, prioritising —
out of the head and into the app, so the things the brain is actually good at have room.
Every feature below is judged on one question: *does this remove a decision, or add one?*

## The one design principle

> **The skeleton never moves. The skin changes every 3 days.**

Muscle memory is the one free win available: the same button in the same place becomes
automatic, and automatic actions don't need activation energy. So novelty goes into colour,
type, texture, sound, and copy voice. It never goes into layout position. That is how the
app stays interesting without forcing a relearn every 72 hours.

## Screens

Five tabs, fixed order, positions never change across themes.

| Tab | Job | Notes |
| --- | --- | --- |
| **NOW** | One task, full screen, nothing else | Default launch screen. Actions: Start / Split / Not now / Nope |
| **IN** | Everything captured, untriaged | Zero required fields to add. Triage is a separate act from capture |
| **DAY** | Today's shape | Hard commitments + routines on a simple timeline. Read-only-ish |
| **ALL** | The full list, on purpose | Behind a deliberate tap. Browse *mode* rotates here (list / deck / roulette) |
| **ME** | Basics, settings, theme pin, the done log | Deliberately thin — see "the app as procrastination object" |

`NOW` never shows a count of what's left. The list is the anxiety source; it stays behind a tap.

## The 3-day style rotation

### Mechanics

Deterministic from the date, so it needs no server state and is identical on every device.

```ts
const PERIOD_DAYS = 3;
const FLIP_HOUR = 4;      // themes change overnight, never mid-session
const EPOCH_DAY = 20454;  // days since 1970-01-01 of launch day

export function themeSlot(now = new Date()): number {
  const shifted = new Date(now.getTime() - FLIP_HOUR * 3_600_000);
  const localDay = Math.floor(
    (shifted.getTime() - shifted.getTimezoneOffset() * 60_000) / 86_400_000,
  );
  return Math.floor((localDay - EPOCH_DAY) / PERIOD_DAYS);
}

export function themeFor(now = new Date()): Theme {
  const slot = themeSlot(now);
  const cycle = Math.floor(slot / THEMES.length);
  const order = seededShuffle(THEMES.length, cycle); // fresh order each full pass
  const i = ((slot % THEMES.length) + THEMES.length) % THEMES.length;
  return THEMES[order[i]];
}
```

The 4am flip matters: a theme that changes at midnight changes *during* a late-night session,
which is disorienting. Reshuffling the order once per full cycle stops the sequence itself
becoming predictable.

### What a theme is

Each theme is a token set applied as CSS custom properties on `:root[data-theme]`; Tailwind
reads the vars, so components are written once and never per-theme.

- **Palette** — ground, surface, ink, muted, hairline, accent, accent-ink, ok, caution
- **Type** — display face + body face (self-hosted, so it works offline)
- **Shape** — radius scale, border weight, shadow style (flat / soft / hard-offset)
- **Density** — comfortable vs compact spacing step
- **Motion** — how much easing and travel transitions get
- **Texture** — flat / grain / gradient wash
- **Voice** — which copy pool the nudges draw from (dry, warm, blunt, silly)

Start with 6 themes; 12 is the target. At 12 themes and a 3-day period a full cycle is 36 days,
long enough that a returning theme feels like a re-release rather than a repeat.

### Guardrails

A theme system with no floor eventually ships an unreadable day. Enforce in `npm test`:

- ink-on-surface ≥ 7:1, muted-on-surface ≥ 4.5:1, accent-ink-on-accent ≥ 4.5:1
- hairline-on-surface ≥ 1.4:1 (visible, not decorative-only)
- every theme defines every token — no inherited holes
- touch targets ≥ 48dp in every density
- `prefers-reduced-motion` collapses the motion token regardless of theme

### Escape hatches

- **Pin** — "keep this one", freezes rotation until unpinned
- **Shuffle now** — for when today's theme grates; advances the slot without waiting
- **Reveal** — first open on a new theme gets a 1-second reveal, so the change registers as a
  small reward rather than "did something break?"

### Rotate the interaction too, not just the paint

Skin-only novelty goes stale in a couple of cycles. So `ALL` also rotates *how* the list is
presented — plain list, swipeable card deck, or roulette ("pick one for me"). `NOW` is exempt.
Its layout is the one thing that must stay identical forever.

## Strategies

Each row: the thing the brain does, and the concrete mechanism that absorbs it.

### Getting started

| Brain | App |
| --- | --- |
| Can't start; the task is a fog | Every task carries a **first step** that is physical and ≤2 minutes. No first step → `NOW` offers "define the first move" instead, which is itself a 20-second task |
| The bar feels too high to begin | **Start dirty** — a 5-minute timer with explicit permission to do it badly. Lowering the quality bar is the single most effective initiation hack there is |
| Multi-step projects read as one impossible blob | **Split** button → Groq decomposes into 3–5 concrete steps, first one physical. Rate-limited |

### Time

| Brain | App |
| --- | --- |
| Time blindness — "later" and "in 20 minutes" feel the same | **Time cushion**: a persistent bar showing minutes until the next hard commitment, always visible on `NOW` |
| Digits are abstract | Timers are **analog** — a draining bar or shrinking pie. Shape is legible pre-verbally in a way `14:32` is not |
| Chronic underestimation | Log estimate vs actual, compute a personal median ratio, then show it *at scheduling time*: "you said 20m → realistically ~45m" |
| Transitions are the hard part, not the task | Pre-alerts at T-15 and T-5 that name the **transition action**, not the event: "stop editing, put shoes on" |
| Hyperfocus eats the body | After 50 minutes of an active session, a **body check** — water / stand / bathroom / eyes. A check, not a stop order |

### Capture

| Brain | App |
| --- | --- |
| Working memory drops it in the 4 seconds before the app opens | Long-press icon → **Quick Capture** shortcut. **Share target** so anything from any app lands in `IN`. **Voice** button, one tap, no confirmation step |
| Forms kill capture | Nothing is required but the text. No project, no date, no priority. Triage happens later or never |

### Choosing

| Brain | App |
| --- | --- |
| "What's most important?" is unanswerable and causes total stall | There is **no priority field**. Ever. Selection is by energy match or pairwise "this or that" |
| Capacity varies wildly hour to hour | One-tap **brain state** — fried / ok / sharp. Tasks are tagged by cognitive load; `NOW` only offers what fits. Fried should surface laundry, not tax paperwork |
| Unmedicated / unfed days get treated like normal days | **Basics** taps on `ME` — meds, water, food, sleep. If meds aren't logged by noon, `NOW` quietly biases toward light tasks |

### Not quitting

| Brain | App |
| --- | --- |
| A broken streak triggers shame, and shame ends the app | The **streak cannot break**. It's a rolling 7-day completion count, never zeroed |
| Habituation kills fixed rewards | **Variable reward** — completion always feels good, and roughly 1 in 5 gives something extra (a theme unlock, a sound, a collectible). Variable ratio is genuinely stickier |
| "I did nothing today" despite doing things | The **done log** is the trophy case: "34 things this week." Concrete evidence against the self-narrative |
| Overdue lists become a wall of accusation | Nothing turns red. Past-due items go quiet, then resurface once as "still want this?" → Keep / Later / Let go |
| A cluttered inbox becomes unfaceable | **Amnesty** — one tap archives all of `IN`, no confirmation shaming, no counter of what was dropped |

### Object permanence

| Brain | App |
| --- | --- |
| Morning and evening sequences have to be re-derived daily | **Routines** as resetting checklists, every item ≤2 min, one card, tap-through, no memory required |
| Tomorrow starts from a cold engine | **Shutdown ritual** ends the day by picking tomorrow's one thing, so `NOW` is already loaded at breakfast |
| Working alone has no friction against drift | **Focus room** — timer plus optional Supabase Realtime presence, so a friend's running timer sits next to yours. Body doubling, two people, free tier |

### Notifications

Budget: **4 per day, maximum.** Copy is drawn from a rotating pool per theme voice, because
identical notification text gets tuned out within about a week. Nudges name an action, never a
status.

## What this deliberately will not have

Each of these is a known failure mode, not an oversight.

- **Priority levels** — ranking is the paralysis, not the cure
- **Streaks that reset to zero** — converts one bad day into abandonment
- **Red badges, overdue counts, "you missed 3 days"** — the page has no red anywhere and neither does the app
- **Nested projects and folders** — organising becomes the procrastination. Flat list, tags, done
- **A points economy** — anything requiring upkeep will be abandoned and then feel like debt
- **Calendar ownership** — read Google Calendar, never replace it
- **Required fields anywhere in capture**

### The app as procrastination object

The real risk isn't a missing feature, it's that tending the app replaces doing the work.
Countermeasures: `ME` stays thin, there is no way to restructure the list into hierarchies,
and there are no customisation knobs beyond pin/shuffle/language. The theme changes *by itself* —
that's the point. Choosing themes would be a trap.

## Data model

Single user, so this stays simple. All tables carry `user_id` + RLS.

```
tasks        id, title, first_step, state (inbox|active|parked|done|cold),
             cognitive_load (light|medium|heavy), context (work|home|errand|phone|computer),
             est_minutes, actual_minutes, soft_due, hard_deadline, project_tag,
             created_at, updated_at, done_at
routines     id, name, slot (morning|evening|shutdown), items jsonb, active
routine_runs id, routine_id, date, checked jsonb
sessions     id, task_id, started_at, ended_at, kind (dirty|focus|room)
basics_log   date, meds, water_count, ate, sleep_hours
rewards_log  id, kind, granted_at
brain_state  id, level (fried|ok|sharp), at
```

Note the absences: no `priority`, no `parent_id`, no `folder_id`.

## Stack

Free tier only, matching what's already familiar.

- **Next.js 16 + TypeScript + Tailwind** — same stack as curious-club, nothing new to learn
- **PWA, local-first** — Dexie over IndexedDB is the source of truth on device; the app opens
  and captures with no network, on the subway, in a lift. Non-negotiable
- **Supabase** — Postgres as sync target, magic-link auth, RLS. Single user means
  last-write-wins on `updated_at` per row is sufficient. Do not build CRDTs
- **Groq** — task splitting only, rate-limited via the same pattern as `lib/rate-limit.ts`
- **Web Push + self-generated VAPID keys** — free
- **Supabase `pg_cron` (every 5 min) → Edge Function → web-push** for scheduled nudges.
  Vercel Hobby cron only fires once a day, so it cannot carry this; `pg_cron` can
- **Self-hosted fonts** — Google Fonts by URL would break offline and the CSP
- **i18n** — JA and EN string tables from day one, toggle on `ME`. Retrofitting bilingual copy
  across 5 screens later is worse than paying for it upfront

## Honest limits

- A PWA **cannot** put a true widget on the Android home screen. Closest available: app
  shortcuts, share target, and a pinned notification. A real widget needs the Capacitor wrapper
  in Phase 4
- Web Push needs the PWA installed, and Android battery optimisation can delay delivery —
  exclude the app from optimisation on day one
- Web Speech API on Android Chrome needs network for recognition; offline capture falls back to typing
- No Play Store fee is needed: install as a PWA, or sideload the APK later

## Phases

Ordered so that the app is genuinely usable at the end of the first one.

1. **Spine** — capture → `IN`, `NOW` with one task, done, offline, installable, theme rotation
   with 6 themes. This alone is more useful than any app currently on the phone.
2. **Time** — time cushion, analog timers, routines, basics taps, shutdown ritual.
3. **Judgment** — brain state + energy matching, Groq split, estimate calibration,
   Google Calendar read-only.
4. **Nudges** — `pg_cron` web push, transition pre-alerts, body checks, notification copy pools.
5. **Optional** — Capacitor wrapper for a real home-screen widget and lock-screen presence.

## Work scope this has to hold

All four kinds go in one list, separated only by `context` and `project_tag`:

- **Channel production** — filming, editing, thumbnails, uploads. Recurring multi-step; the
  natural fit for routine templates plus Split.
- **Client / employer work** — externally set deadlines. The only things that get `hard_deadline`,
  which is what makes hard deadlines legible instead of drowning in soft ones.
- **Admin & logistics** — bills, appointments, paperwork, cleaning. Mostly light-load tasks;
  this is the pool `NOW` draws from on fried days.
- **Learning / personal projects** — no external deadline, so they silently never happen.
  These get protected: the roulette mode in `ALL` is weighted toward them, and the shutdown
  ritual asks for one of them by name once a week.
