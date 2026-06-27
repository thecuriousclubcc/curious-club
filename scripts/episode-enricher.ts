import Groq from 'groq-sdk'
import { existsSync, readFileSync } from 'fs'
import { mkdir, readFile, writeFile } from 'fs/promises'
import path from 'path'
import { fileURLToPath } from 'url'
import { videos, type Video } from '../data/videos'
import type { Enrichment } from '../lib/enrichment'
import {
  appendVideosToDataFile,
  findNewLongFormEntries,
  parseRssEntries,
  type RssVideoEntry,
  videoFromRssEntry,
  youtubeRssUrl,
} from './episode-enricher-core'

function loadEnvLocal() {
  try {
    const content = readFileSync(path.join(process.cwd(), '.env.local'), 'utf-8')
    for (const line of content.split('\n')) {
      const trimmed = line.trim()
      if (!trimmed || trimmed.startsWith('#')) continue

      const eqIdx = trimmed.indexOf('=')
      if (eqIdx === -1) continue

      const key = trimmed.slice(0, eqIdx).trim()
      const value = trimmed.slice(eqIdx + 1).trim().replace(/^['"]|['"]$/g, '')
      if (key && value && !process.env[key]) process.env[key] = value
    }
  } catch {
    // .env.local is optional for the no-new-episodes and verify flows.
  }
}

async function fetchRssEntries() {
  const channelId = process.env.YOUTUBE_CHANNEL_ID
  const res = await fetch(youtubeRssUrl(channelId), { cache: 'no-store' })
  if (!res.ok) throw new Error(`YouTube RSS returned ${res.status}`)
  return parseRssEntries(await res.text())
}

function extractJson(text: string): string {
  return text
    .replace(/^```json\s*/i, '')
    .replace(/^```\s*/i, '')
    .replace(/```$/i, '')
    .trim()
}

async function summarizeWithGroq(video: { youtubeId: string; title: string; description: string }) {
  const groq = new Groq({ apiKey: process.env.GROQ_API_KEY })
  const completion = await groq.chat.completions.create({
    model: process.env.GROQ_MODEL ?? 'llama-3.3-70b-versatile',
    messages: [
      {
        role: 'user',
        content: `あなたは「The Curious Club（キュリクラ）」というYouTubeチャンネルのコンテンツアナリストです。
このチャンネルは現役医学生が医療・ビジネス・社会など分野を問わず"熱を持って生きる人"にインタビューするプロジェクトです。

以下の新エピソード情報を分析し、視聴者にとって価値ある情報を出力してください。

タイトル: ${video.title}
説明文: ${video.description}

以下のJSONスキーマに従って、有効なJSONのみを返してください（説明や前置きは不要です）:
{
  "summary": "3文以内でエピソードの核心を伝える日本語要約",
  "keyThemes": ["主要テーマタグ（最大5つ）"],
  "keyQuotes": ["印象的な発言やコンセプト（最大3つ）"],
  "careerInsights": ["キャリア・人生への示唆（最大5つ）"],
  "suggestedQuestions": ["視聴後に考えるべき問い（最大3つ）"]
}`,
      },
    ],
    max_tokens: 2048,
    temperature: 0.7,
  })

  const content = completion.choices[0]?.message?.content ?? ''
  const parsed = JSON.parse(extractJson(content)) as Omit<Enrichment, 'videoId' | 'generatedAt'>

  return {
    videoId: video.youtubeId,
    ...parsed,
    generatedAt: new Date().toISOString(),
  } satisfies Enrichment
}

async function writeEnrichment(enrichment: Enrichment, cwd = process.cwd()) {
  const enrichmentsDir = path.join(cwd, 'public', 'data', 'enrichments')
  await mkdir(enrichmentsDir, { recursive: true })
  await writeFile(
    path.join(enrichmentsDir, `${enrichment.videoId}.json`),
    `${JSON.stringify(enrichment, null, 2)}\n`,
    'utf-8',
  )
}

export function findVideosMissingEnrichment<T extends Pick<Video, 'youtubeId'>>(
  allVideos: T[],
  cwd = process.cwd(),
) {
  return allVideos.filter(
    (video) => !existsSync(path.join(cwd, 'public', 'data', 'enrichments', `${video.youtubeId}.json`)),
  )
}

function uniqueVideosByYoutubeId(allVideos: Video[]) {
  return Array.from(new Map(allVideos.map((video) => [video.youtubeId, video])).values())
}

interface RunEpisodeEnricherOptions {
  cwd?: string
  dataFilePath?: string
  entries?: RssVideoEntry[]
  videos?: Video[]
  groqApiKey?: string
  log?: Pick<Console, 'log' | 'error'>
  write?: (message: string) => void
  summarize?: typeof summarizeWithGroq
}

export async function runEpisodeEnricher(options: RunEpisodeEnricherOptions = {}) {
  const cwd = options.cwd ?? process.cwd()
  const log = options.log ?? console
  const write = options.write ?? ((message: string) => process.stdout.write(message))
  const currentVideos = options.videos ?? videos
  const entries = options.entries ?? (await fetchRssEntries())
  const newEntries = findNewLongFormEntries(entries, currentVideos)
  if (newEntries.length === 0) {
    log.log(`OK: no new long-form episodes found in YouTube RSS (${entries.length} feed entries).`)
  }

  const newVideos = newEntries.map((entry, index) => videoFromRssEntry(entry, currentVideos, index))
  const dataFilePath = options.dataFilePath ?? path.join(cwd, 'data', 'videos.ts')

  if (newVideos.length > 0) {
    const currentDataFile = await readFile(dataFilePath, 'utf-8')
    const nextDataFile = appendVideosToDataFile(currentDataFile, newVideos)

    if (nextDataFile !== currentDataFile) {
      await writeFile(dataFilePath, nextDataFile, 'utf-8')
      log.log(`Updated data/videos.ts with ${newVideos.length} new long-form episode(s).`)
    }
  }

  const pendingSummaries = findVideosMissingEnrichment(
    uniqueVideosByYoutubeId([...currentVideos, ...newVideos]),
    cwd,
  )

  if (pendingSummaries.length === 0) {
    log.log('OK: all episodes in data/videos.ts have enrichment JSON files.')
    return { appended: newVideos.length, enriched: 0, pending: 0, exitCode: 0 }
  }

  if (!(options.groqApiKey ?? process.env.GROQ_API_KEY)) {
    log.error(
      `MISSING: GROQ_API_KEY is not set. Skipped ${pendingSummaries.length} missing summary file(s).`,
    )
    return { appended: newVideos.length, enriched: 0, pending: pendingSummaries.length, exitCode: 1 }
  }

  const summarize = options.summarize ?? summarizeWithGroq
  for (const video of pendingSummaries) {
    write(`Summarizing ${video.youtubeId} ${video.title.slice(0, 60)}... `)
    const enrichment = await summarize(video)
    await writeEnrichment(enrichment, cwd)
    log.log('OK')
  }

  log.log(`OK: enriched ${pendingSummaries.length} episode(s).`)
  return {
    appended: newVideos.length,
    enriched: pendingSummaries.length,
    pending: 0,
    exitCode: 0,
  }
}

async function main() {
  loadEnvLocal()
  const result = await runEpisodeEnricher()
  if (result.exitCode !== 0) process.exit(result.exitCode)
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : error)
    process.exit(1)
  })
}
