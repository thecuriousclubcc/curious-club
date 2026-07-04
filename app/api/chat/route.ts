import { NextRequest } from 'next/server'
import Groq from 'groq-sdk'
import { getAllVideos } from '@/lib/videos'
import { getEnrichment } from '@/lib/enrichment'
import { rateLimit, clientIp } from '@/lib/rate-limit'

// Lazy init so builds don't fail when GROQ_API_KEY is absent
function getGroq() { return new Groq({ apiKey: process.env.GROQ_API_KEY }) }

// Abuse guards — keep the free Groq quota safe
const RATE_LIMIT = 10 // requests
const RATE_WINDOW_MS = 60_000 // per minute per IP
const MAX_MESSAGES = 12
const MAX_MESSAGE_CHARS = 1000

// Building the system prompt reads every enrichment file; cache it instead of
// rebuilding on each message
const PROMPT_TTL_MS = 60 * 60 * 1000
let cachedPrompt: { value: string; builtAt: number } | null = null

async function buildSystemPrompt(): Promise<string> {
  if (cachedPrompt && Date.now() - cachedPrompt.builtAt < PROMPT_TTL_MS) {
    return cachedPrompt.value
  }

  const videos = await getAllVideos()

  const enrichments = await Promise.all(
    videos.map(async (v) => {
      const e = await getEnrichment(v.youtubeId)
      return {
        title: v.title,
        youtubeId: v.youtubeId,
        tags: v.tags,
        summary: e?.summary ?? v.description.slice(0, 300),
        keyThemes: e?.keyThemes ?? [],
        careerInsights: e?.careerInsights ?? [],
      }
    }),
  )

  const prompt = `あなたは「The Curious Club（キュリクラ）」のAIアシスタントです。
現役医学生が分野を超えて"熱を持って生きる人"にインタビューするYouTubeチャンネルのナビゲーターとして振る舞ってください。

以下はこのチャンネルで公開されているエピソードの一覧です：

${JSON.stringify(enrichments, null, 2)}

回答のガイドライン:
- このチャンネルのエピソードに関連する質問にのみ答えてください
- エピソードを推薦する際は必ずタイトルと youtubeId を明記し、/videos/[youtubeId] へのリンクを示してください
- 関係のない話題には丁寧に断りを入れてください
- 回答は日本語で、簡潔かつ親しみやすいトーンで行ってください
- Markdownは使用せず、プレーンテキストで回答してください`

  cachedPrompt = { value: prompt, builtAt: Date.now() }
  return prompt
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

// --- Quricula Brain grounding: real transcript quotes with timestamps ---

interface BrainSource {
  video_title: string
  youtube_id: string
  published_on: string | null
  start_sec: number
  end_sec: number
  speaker: string | null
  quote: string
}

function mmss(sec: number): string {
  const s = Math.floor(sec)
  const m = Math.floor(s / 60)
  return `${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

async function searchBrain(q: string): Promise<BrainSource[]> {
  const url = process.env.SUPABASE_URL
  const key = process.env.SUPABASE_ANON_KEY
  if (!url || !key || q.trim().length < 2) return []
  try {
    const r = await fetch(`${url}/rest/v1/rpc/brain_search`, {
      method: 'POST',
      headers: {
        apikey: key,
        Authorization: `Bearer ${key}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ q: q.slice(0, 100), max_results: 5 }),
      cache: 'no-store',
    })
    if (!r.ok) return []
    return (await r.json()) as BrainSource[]
  } catch {
    return []
  }
}

function groundingMessage(sources: BrainSource[]): string {
  const excerpts = sources
    .map(
      (s, i) =>
        `[${i + 1}] 動画「${s.video_title}」 ${mmss(s.start_sec)}〜 ${s.speaker ?? '出演者'}:「${s.quote.slice(0, 200)}」`,
    )
    .join('\n')
  return `参考情報: ユーザーの質問に関連する、動画内の実際の発言（文字起こし検索の結果）:

${excerpts}

これらが質問に関連する場合は発言内容を根拠として使い、本文中で「どの動画の何分何秒あたりか」（例: 「◯◯」の12:34あたり）を示してください。発言にないことを発言として紹介しないでください。該当箇所への再生リンクはUI側で自動表示されるため、URLは書かないでください。関連しない場合は無視して構いません。`
}

function validateMessages(input: unknown): ChatMessage[] | null {
  if (!Array.isArray(input) || input.length === 0 || input.length > MAX_MESSAGES) {
    return null
  }
  const messages: ChatMessage[] = []
  for (const m of input) {
    if (
      !m ||
      typeof m !== 'object' ||
      (m.role !== 'user' && m.role !== 'assistant') ||
      typeof m.content !== 'string' ||
      m.content.length === 0 ||
      m.content.length > MAX_MESSAGE_CHARS
    ) {
      return null
    }
    messages.push({ role: m.role, content: m.content })
  }
  return messages
}

export async function POST(req: NextRequest) {
  const { ok } = rateLimit(`chat:${clientIp(req)}`, RATE_LIMIT, RATE_WINDOW_MS)
  if (!ok) {
    return new Response('rate limit exceeded', { status: 429 })
  }

  const body = await req.json().catch(() => null)
  const messages = validateMessages(body?.messages)
  if (!messages) {
    return new Response('invalid messages', { status: 400 })
  }

  const lastUser = [...messages].reverse().find((m) => m.role === 'user')
  const [systemPrompt, sources] = await Promise.all([
    buildSystemPrompt(),
    searchBrain(lastUser?.content ?? ''),
  ])

  const stream = await getGroq().chat.completions.create({
    model: 'llama-3.3-70b-versatile',
    messages: [
      { role: 'system', content: systemPrompt },
      ...(sources.length
        ? [{ role: 'system' as const, content: groundingMessage(sources) }]
        : []),
      ...messages,
    ],
    max_tokens: 1024,
    temperature: 0.7,
    stream: true,
  })

  const encoder = new TextEncoder()
  const readable = new ReadableStream({
    async start(controller) {
      try {
        // Sources first so the widget can render timestamp chips under the reply
        if (sources.length) {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ sources })}\n\n`))
        }
        for await (const chunk of stream) {
          const text = chunk.choices[0]?.delta?.content ?? ''
          if (text) {
            controller.enqueue(
              encoder.encode(`data: ${JSON.stringify({ text })}\n\n`),
            )
          }
          if (chunk.choices[0]?.finish_reason) {
            controller.enqueue(encoder.encode('data: [DONE]\n\n'))
            controller.close()
          }
        }
      } catch {
        controller.enqueue(encoder.encode('data: [DONE]\n\n'))
        controller.close()
      }
    },
  })

  return new Response(readable, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      Connection: 'keep-alive',
    },
  })
}
