import { NextRequest } from 'next/server'
import Groq from 'groq-sdk'
import { videos as staticVideos } from '@/data/videos'
import { getChannelVideos } from '@/lib/youtube'
import { getEnrichment } from '@/lib/enrichment'

const groq = new Groq({ apiKey: process.env.GROQ_API_KEY })
const CHANNEL_ID = process.env.YOUTUBE_CHANNEL_ID ?? ''

async function buildSystemPrompt(): Promise<string> {
  const liveVideos = CHANNEL_ID ? await getChannelVideos(CHANNEL_ID).catch(() => []) : []
  const videos = liveVideos.length > 0 ? liveVideos : staticVideos

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

  return `あなたは「The Curious Club（キュリクラ）」のAIアシスタントです。
現役医学生が分野を超えて"熱を持って生きる人"にインタビューするYouTubeチャンネルのナビゲーターとして振る舞ってください。

以下はこのチャンネルで公開されているエピソードの一覧です：

${JSON.stringify(enrichments, null, 2)}

回答のガイドライン:
- このチャンネルのエピソードに関連する質問にのみ答えてください
- エピソードを推薦する際は必ずタイトルと youtubeId を明記し、/videos/[youtubeId] へのリンクを示してください
- 関係のない話題には丁寧に断りを入れてください
- 回答は日本語で、簡潔かつ親しみやすいトーンで行ってください
- Markdownは使用せず、プレーンテキストで回答してください`
}

export async function POST(req: NextRequest) {
  const body = await req.json()
  const messages = body.messages as { role: 'user' | 'assistant'; content: string }[]

  if (!messages || messages.length === 0) {
    return new Response('messages required', { status: 400 })
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
