import { NextRequest, NextResponse } from 'next/server'
import Groq from 'groq-sdk'
import { saveEnrichment, type Enrichment } from '@/lib/enrichment'

// Lazy init so builds don't fail when GROQ_API_KEY is absent
function getGroq() { return new Groq({ apiKey: process.env.GROQ_API_KEY }) }

export async function POST(req: NextRequest) {
  const authHeader = req.headers.get('x-enrich-secret')
  if (authHeader !== process.env.ENRICH_SECRET) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 })
  }

  const body = await req.json()
  const { videoId, title, description } = body as {
    videoId: string
    title: string
    description: string
  }

  if (!videoId || !title || !description) {
    return NextResponse.json({ error: 'missing required fields' }, { status: 400 })
  }

  const prompt = `あなたは「The Curious Club（キュリクラ）」というYouTubeチャンネルのコンテンツアナリストです。
このチャンネルは現役医学生が医療・ビジネス・社会など分野を問わず"熱を持って生きる人"にインタビューするプロジェクトです。

以下のエピソード情報を分析し、視聴者にとって価値ある情報を出力してください。

タイトル: ${title}
説明文: ${description}

以下のJSONスキーマに従って、有効なJSONのみを返してください（説明や前置きは不要です）:
{
  "summary": "3文以内でエピソードの核心を伝える日本語要約",
  "keyThemes": ["主要テーマタグ（最大5つ）"],
  "keyQuotes": ["印象的な発言やコンセプト（最大3つ）"],
  "careerInsights": ["キャリア・人生への示唆（最大5つ）"],
  "suggestedQuestions": ["視聴後に考えるべき問い（最大3つ）"]
}`

  const completion = await getGroq().chat.completions.create({
    model: 'llama-3.3-70b-versatile',
    messages: [{ role: 'user', content: prompt }],
    max_tokens: 2048,
    temperature: 0.7,
  })

  const text = completion.choices[0]?.message?.content ?? ''
  const raw = text.replace(/^```json\n?|```$/g, '').trim()
  const parsed = JSON.parse(raw) as Omit<Enrichment, 'videoId' | 'generatedAt'>
  const enrichment: Enrichment = {
    videoId,
    ...parsed,
    generatedAt: new Date().toISOString(),
  }

  await saveEnrichment(enrichment)
  return NextResponse.json(enrichment)
}
