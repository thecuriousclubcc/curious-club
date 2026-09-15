# Access register

Every account, key, and asset this project depends on — what it is, who owns
it, and what breaks if access is lost. **No secrets in this file.** Secrets
live in `.env.local` (gitignored) and in Vercel's environment variables.

Audited 2026-09-15. Re-check when a service is added or an owner changes.

## Identities

Everything below is reachable only through these logins. They are the real
root of access — a key can be re-issued, an account cannot.

| Identity | Controls | Notes |
|---|---|---|
| `thecuriousclub.cc@gmail.com` | YouTube channel, Google Drive (masters, contracts, invoices), Google Forms, GA4, and the logins for Vercel / Supabase / Groq / Resend / Cloudflare if they were created with "Sign in with Google" | Single point of failure. A personal Gmail, not a company-owned domain. |
| GitHub `thecuriousclubcc` | This repository | Personal account, not an organization. Sole admin, no other collaborators. |
| `robinkuroiwa@gmail.com` | Operator account used for tooling sessions | Distinct from the channel identity above. |

Recovery for the Google identity (2FA, backup codes, recovery phone and
address) is the highest-value thing to keep current. Everything else is
downstream of it.

## Services

| Service | Used for | Tier | Env vars | If access is lost |
|---|---|---|---|---|
| Vercel | Hosting, deploys, `curious-club.vercel.app` | Free | — | Site goes down. Redeployable from this repo in minutes. |
| Supabase (`cc-brain`) | Transcript corpus + `brain_search` RPC | Free | `SUPABASE_URL`, `SUPABASE_ANON_KEY` | `/brain` and grounded chat return 503. **The transcript corpus is not backed up anywhere else.** |
| Groq | Chat, `/brain` answers, enrichment, X copy | Free | `GROQ_API_KEY`, `GROQ_MODEL` | AI features degrade; site still serves. |
| Resend | Contact form, newsletter list | Free | `RESEND_API_KEY`, `RESEND_AUDIENCE_ID` | Inbound enquiries silently fail. Subscriber list is held only in Resend. |
| Cloudflare Turnstile | Contact form bot protection | Free | `NEXT_PUBLIC_TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY` | Contact form rejects every submission. |
| YouTube Data API | View counts, durations | Free quota | `YOUTUBE_API_KEY`, `YOUTUBE_CHANNEL_ID` | Falls back to public RSS automatically. Low risk. |
| X (Twitter) API | `npm run x:post` | Free | `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET` | Syndication stops. Offline script only. |
| Google Analytics 4 | Traffic stats (`G-WXL5VWXWYN`) | Free | hardcoded in `app/layout.tsx` | Historical stats lost unless exported. |

## Public identifiers

Not secret, but needed to rebuild or prove ownership:

- YouTube channel: `@TheCuriousClub_CC` / `UCtMsMejHNPL_PGVv_iJ2xNw`
- X: `@becurious4ever` · Instagram: `@thecuriousclub_cc`
- note: `note.com/thecuriousclub` · Spotify show: `2txhDE2vizjPRoOXYKMYCd`
- Contact destination: `thecuriousclub.cc@gmail.com`
- Sender address: `onboarding@resend.dev` (Resend's shared sandbox sender — no
  custom domain is verified, so delivery only works to the Resend account's
  own address)

## Assets and where they live

| Asset | Location | Replaceable? |
|---|---|---|
| Published videos | YouTube | Yes, from masters |
| Raw masters (~8.3 GiB, 42 files) | Google Drive only | **No** |
| Transcript corpus | Supabase `cc-brain` only | Only by re-transcribing |
| Video catalog + AI summaries | `data/videos.ts` (in git) | Yes |
| X post queue | `data/x-queue.json` (in git) | Yes |
| Contracts, invoices | Google Drive only | **No** |
| Newsletter subscribers | Resend only | **No** |
| Site code | This repo + local clones | Yes |

Assets marked **No** exist in exactly one place. That is the whole risk.

## Assets owned by other people

These are shared *to* the channel account and can be revoked by their owner
at any time — they are borrowed, not held:

- `投稿文案` spreadsheet — owned by `harubinnoiwa@gmail.com`, actively used
- Clinic materials and signature images — owned by
  `kagoshima.mitsui.chuoh@gmail.com`, `n.naoko1023@gmail.com`
- Screen recording — owned by `nakanot82@gmail.com`

Anything needed long-term should be re-created under the channel's own
ownership. Client material is a separate question: retention may be limited
by the 業務委託契約書, so check the contract before copying it anywhere.

## Rotating a key

1. Re-issue in the provider's dashboard.
2. Update Vercel > Project Settings > Environment Variables.
3. Redeploy (env changes do not apply to existing deployments).
4. Update `.env.local` locally.

`.env.local.example` lists every variable the code reads and which route
reads it. Full-history secret scan on 2026-09-15 found no committed
credentials; keep it that way.
