import { NextRequest, NextResponse } from 'next/server'
import Groq from 'groq-sdk'
import { rateLimit, clientIp } from '@/lib/rate-limit'

// Grounded AI answer over video transcripts. The no-fabrication guarantee is
// enforced in code, not prompt: every citation's quote must be a literal
// substring of the chunk it points to, or it is dropped.

function getGroq() { return new Groq({ apiKey: process.env.GROQ_API_KEY }) }

const RATE_LIMIT = 5
const RATE_WINDOW_MS = 60_000

interface BrainHit {
  video_title: string
  youtube_id: string
  published_on: string | null
  start_sec: number
  end_sec: number
  speaker: string | null
  quote: string
}

const SYSTEM = `あなたは「The Curious Club（キュリクラ）」の動画内検索アシスタント。ルールは絶対:
1. 回答は渡された抜粋内の発言のみに基づく。推測・一般知識で補完しない。
2. すべての主張に [n] 形式で引用番号を付ける。
3. 該当する発言がない場合は answer を「該当する発言は見つかりませんでした」とする。
4. 引用(quote)は抜粋から一字一句そのまま抜き出す。要約・改変禁止。
5. 医学的な正否は判断しない。「誰がこう発言した」という事実のみ扱う。
必ず次のJSONだけを出力: {"answer": "...", "citations": [{"n": 1, "quote": "..."}]}`

const norm = (s: string) => s.replace(/\s+/g, '')

export async function POST(req: NextRequest) {
  const { ok } = rateLimit(`brain-ask:${clientIp(req)}`, RATE_LIMIT, RATE_WINDOW_MS)
  if (!ok) return NextResponse.json({ error: 'rate limit exceeded' }, { status: 429 })

  const body = await req.json().catch(() => null)
  const query = typeof body?.query === 'string' ? body.query.trim() : ''
  if (query.length < 2 || query.length > 100) {
    return NextResponse.json({ answer: null, sources: [] })
  }

  const url = process.env.SUPABASE_URL
  const key = process.env.SUPABASE_ANON_KEY
  if (!url || !key || !process.env.GROQ_API_KEY) {
    return NextResponse.json({ error: 'not configured' }, { status: 503 })
  }

  const r = await fetch(`${url}/rest/v1/rpc/brain_search`, {
    method: 'POST',
    headers: { apikey: key, Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ q: query, max_results: 8 }),
    cache: 'no-store',
  })
  if (!r.ok) return NextResponse.json({ error: 'search failed' }, { status: 502 })
  const hits: BrainHit[] = await r.json()

  const notFound = { answer: '該当する発言は見つかりませんでした', sources: [] }
  if (!hits.length) return NextResponse.json(notFound)

  const ctx = hits
    .map(
      (h, i) =>
        `[${i + 1}] 動画「${h.video_title}」 話者:${h.speaker ?? '不明'}\n「${h.quote.slice(0, 300)}」`,
    )
    .join('\n\n')

  const completion = await getGroq().chat.completions.create({
    model: 'llama-3.3-70b-versatile',
    response_format: { type: 'json_object' },
    temperature: 0.2,
    max_tokens: 1024,
    messages: [
      { role: 'system', content: SYSTEM },
      { role: 'user', content: `質問: ${query}\n\n抜粋:\n${ctx}` },
    ],
  })

  let parsed: { answer?: string; citations?: { n?: number; quote?: string }[] }
  try {
    parsed = JSON.parse(completion.choices[0]?.message?.content ?? '{}')
  } catch {
    return NextResponse.json(notFound)
  }

  // Machine verification: quote must literally exist in the cited chunk
  const verified = (parsed.citations ?? []).filter(
    (c) =>
      typeof c.n === 'number' &&
      c.n >= 1 &&
      c.n <= hits.length &&
      c.quote &&
      norm(hits[c.n - 1].quote).includes(norm(c.quote)),
  )
  if (!verified.length) return NextResponse.json(notFound)

  return NextResponse.json({
    answer: parsed.answer ?? '',
    sources: verified.map((c) => {
      const h = hits[(c.n as number) - 1]
      return {
        quote: c.quote,
        video_title: h.video_title,
        youtube_id: h.youtube_id,
        published_on: h.published_on,
        start_sec: h.start_sec,
        end_sec: h.end_sec,
        speaker: h.speaker,
      }
    }),
  })
}
