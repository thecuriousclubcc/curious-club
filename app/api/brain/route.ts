import { NextRequest, NextResponse } from 'next/server'
import { rateLimit, clientIp } from '@/lib/rate-limit'

// Keyword search over video transcripts (Quricula Brain, Supabase RPC).
// Returns only YouTube-published content with public-safe fields.
const RATE_LIMIT = 20
const RATE_WINDOW_MS = 60_000
const MAX_QUERY_CHARS = 100

export async function GET(req: NextRequest) {
  const query = req.nextUrl.searchParams.get('q')?.trim()
  if (!query || query.length < 2 || query.length > MAX_QUERY_CHARS) {
    return NextResponse.json({ hits: [] })
  }

  const { ok } = rateLimit(`brain:${clientIp(req)}`, RATE_LIMIT, RATE_WINDOW_MS)
  if (!ok) {
    return NextResponse.json({ error: 'rate limit exceeded' }, { status: 429 })
  }

  const url = process.env.SUPABASE_URL
  const key = process.env.SUPABASE_ANON_KEY
  if (!url || !key) {
    return NextResponse.json({ error: 'brain search is not configured' }, { status: 503 })
  }

  const r = await fetch(`${url}/rest/v1/rpc/brain_search`, {
    method: 'POST',
    headers: {
      apikey: key,
      Authorization: `Bearer ${key}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ q: query, max_results: 10 }),
    cache: 'no-store',
  })
  if (!r.ok) {
    return NextResponse.json({ error: 'search failed' }, { status: 502 })
  }
  const rows: {
    video_title: string
    youtube_id: string
    published_on: string | null
    start_sec: number
    end_sec: number
    speaker: string | null
    quote: string
  }[] = await r.json()

  return NextResponse.json({ hits: rows })
}
