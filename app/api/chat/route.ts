import { NextRequest } from 'next/server'
import Groq from 'groq-sdk'
import { getAllVideos } from '@/lib/videos'
import { getEnrichment } from '@/lib/enrichment'
import { rateLimit, clientIp } from '@/lib/rate-limit'

const groq = new Groq({ apiKey: process.env.GROQ_API_KEY })

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

  const systemPrompt = await buildSystemPrompt()

  const stream = await groq.chat.completions.create({
    model: 'llama-3.3-70b-versatile',
    messages: [{ role: 'system', content: systemPrompt }, ...messages],
    max_tokens: 1024,
    temperature: 0.7,
    stream: true,
  })

  const encoder = new TextEncoder()
  const readable = new ReadableStream({
    async start(controller) {
      try {
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
