import { NextRequest, NextResponse } from 'next/server'
import Groq from 'groq-sdk'
import { videos as staticVideos } from '@/data/videos'
import { getChannelVideos } from '@/lib/youtube'
import { getEnrichment } from '@/lib/enrichment'

const groq = new Groq({ apiKey: process.env.GROQ_API_KEY })

const CHANNEL_ID = process.env.YOUTUBE_CHANNEL_ID ?? ''

async function getAllVideos() {
  const liveVideos = CHANNEL_ID ? await getChannelVideos(CHANNEL_ID).catch(() => []) : []
  return liveVideos.length > 0 ? liveVideos : staticVideos
}

export async function GET(req: NextRequest) {
  const query = req.nextUrl.searchParams.get('q')?.trim()
  if (!query || query.length < 2) {
    return NextResponse.json({ results: [] })
  }

  const videos = await getAllVideos()

  const episodeIndex = await Promise.all(
    videos.map(async (v) => {
      const enrichment = await getEnrichment(v.youtubeId)
      return {
        youtubeId: v.youtubeId,
        title: v.title,
        tags: v.tags,
        summary: enrichment?.summary ?? v.description.slice(0, 200),
        keyThemes: enrichment?.keyThemes ?? [],
      }
    }),
  )

  const prompt = `以下のエピソード一覧から、ユーザーの検索クエリに最も関連するものをランキング順に返してください。

検索クエリ: ${query}

エピソード一覧:
${JSON.stringify(episodeIndex, null, 2)}

指示:
- 関連性の高い順に youtubeId の配列を返してください
- 関連性がないと判断したエピソードは除外してください
- 最大10件まで返してください
- 以下のJSON形式のみで返してください（説明不要）:
{"rankedIds": ["youtubeId1", "youtubeId2"]}`

  const completion = await groq.chat.completions.create({
    model: 'llama-3.3-70b-versatile',
    messages: [{ role: 'user', content: prompt }],
    max_tokens: 256,
    temperature: 0,
  })

  try {
    const text = completion.choices[0]?.message?.content ?? ''
    const raw = text.replace(/^```json\n?|```$/g, '').trim()
    const { rankedIds } = JSON.parse(raw) as { rankedIds: string[] }
    const results = rankedIds
      .map((id) => videos.find((v) => v.youtubeId === id))
      .filter(Boolean)
    return NextResponse.json({ results })
  } catch {
    return NextResponse.json({ results: [] })
  }
}
