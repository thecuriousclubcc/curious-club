# CLAUDE.md — curious-club

Public site for The Curious Club（キュリクラ）YouTube channel. **Live in production on Vercel** — treat every change as user-facing.

## Hard constraints
- **Free tier only.** No paid APIs, paid plans, or paid infra. Vercel free, Supabase free, Groq free tier. Reject approaches that require paid upgrades.
- Site copy is Japanese; code/comments in English.

## Stack
- Next.js 16 App Router + TypeScript + Tailwind CSS (v3), deployed on Vercel.
- Supabase (cc-brain project) via `brain_search` RPC — powers `/brain` transcript search and Ask-the-Club chat grounding. Anon key only; RLS enforced server-side.
- Groq SDK for chat; Resend for contact form; Turnstile for bot protection; twitter-api-v2 for X syndication.

## Commands
- `npm run dev` / `npm run build` / `npm run lint`
- `npm test` — node test runner via tsx over `tests/**/*.test.ts`
- `npm run episode:enrich` / `episode:verify` — RSS episode-summary enrichment agent
- `npm run x:syndicate` / `x:post` — X (Twitter) queue build + post (queue state in `data/x-queue.json`)

## Layout
- `app/` — routes: `/`, `/videos`, `/about`, `/contact`, `/brain` (動画内検索 + inline YouTube player seeking to the hit second), `app/api/` route handlers
- `lib/` — shared: `site.ts` (site metadata), `videos.ts` + `data/videos.ts` (video catalog), `youtube.ts`, `rate-limit.ts`, `enrichment.ts`
- `scripts/` — offline agents run manually via npm scripts, not deployed

## Conventions
- Secrets in `.env.local` only (gitignored); never hardcode keys.
- API routes that call external services must rate-limit (see `lib/rate-limit.ts`) — free-tier quotas are the budget.
- Run `npm run lint && npm test && npm run build` before committing; there is no CI yet, so local checks are the gate.
