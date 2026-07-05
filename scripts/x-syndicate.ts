// X (Twitter) syndication — copy generator → review queue.
//
// Build step 1 of the X automation plan (see the harness playbook
// `playbooks/x-marketing.md`): for new/recent YouTube videos (long-form +
// Shorts) this generates Japanese X copy with Groq/Claude and writes it to a
// human-review queue at `data/x-queue.json`. It DOES NOT post anything — a later
// step consumes `status: "approved"` drafts and posts via the X API.
//
// Usage:
//   npm run x:syndicate              # latest 3 videos missing from the queue
//   npm run x:syndicate -- --limit=5 # latest 5
//   npm run x:syndicate -- --id=XubOV11LSnw   # one specific youtubeId
//   npm run x:syndicate -- --all     # every known video not yet queued
//   npm run x:syndicate -- --force   # regenerate even if already queued

import Groq from 'groq-sdk'
import { existsSync, readFileSync } from 'fs'
import { mkdir, readFile, writeFile } from 'fs/promises'
import path from 'path'
import { fileURLToPath } from 'url'
import { videos, type Video } from '../data/videos'
import { getEnrichment, type Enrichment } from '../lib/enrichment'
import {
  isShort,
  parseRssEntries,
  videoFromRssEntry,
  youtubeRssUrl,
  type RssVideoEntry,
} from './episode-enricher-core'

const QUEUE_PATH = path.join('data', 'x-queue.json')

export interface XSyndicationDraft {
  youtubeId: string
  videoTitle: string
  youtubeUrl: string
  isShort: boolean
  status: 'pending_review' | 'approved' | 'posted' | 'skip'
  generatedAt: string
  /**
   * Local path to the native video (.mp4) to upload with the launch post.
   * Seeded as a suggestion; the reviewer fills in the real file before approving.
   * If empty/missing at post time, the launch post goes out as text-only.
   */
  mediaPath: string
  /** Native-video caption (upload the .mp4; keep the link OUT of this post). */
  launchPost: string
  /** Reply tweet that carries the YouTube link (X downranks links in the main post). */
  linkReply: string
  /** 「印象的だった3つの話」— 3 tweets, post as a thread. */
  thread: string[]
  /** Text for a 名言カード quote graphic. */
  quoteCard: { quote: string; attribution: string }
  /** Pre-written, pre-tagged post the guest can reshare with zero effort. */
  guestResharePost: string
  hashtags: string[]
  /** Manual TODOs before approving (e.g. fill the guest's @handle, attach mp4). */
  reviewerNotes: string[]
}

export interface XQueue {
  updated: string
  drafts: XSyndicationDraft[]
}

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
    // .env.local is optional.
  }
}

function extractJson(text: string): string {
  return text
    .replace(/^```json\s*/i, '')
    .replace(/^```\s*/i, '')
    .replace(/```$/i, '')
    .trim()
}

async function fetchRssEntries(): Promise<RssVideoEntry[]> {
  const channelId = process.env.YOUTUBE_CHANNEL_ID
  try {
    const res = await fetch(youtubeRssUrl(channelId), { cache: 'no-store' })
    if (!res.ok) throw new Error(`YouTube RSS returned ${res.status}`)
    return parseRssEntries(await res.text())
  } catch {
    // Offline / rate-limited: fall back to the committed video list only.
    return []
  }
}

type SyndicationTarget = Pick<Video, 'youtubeId' | 'title' | 'description' | 'youtubeUrl'> & {
  isShort: boolean
}

/** Merge RSS entries (catches brand-new uploads incl. Shorts) with data/videos.ts. */
export function collectTargets(
  rssEntries: RssVideoEntry[],
  knownVideos: Video[] = videos,
): SyndicationTarget[] {
  const byId = new Map<string, SyndicationTarget>()

  for (const video of knownVideos) {
    byId.set(video.youtubeId, {
      youtubeId: video.youtubeId,
      title: video.title,
      description: video.description,
      youtubeUrl: video.youtubeUrl,
      isShort: isShort(video),
    })
  }

  for (const entry of rssEntries) {
    if (byId.has(entry.youtubeId)) continue
    const v = videoFromRssEntry(entry, knownVideos)
    byId.set(entry.youtubeId, {
      youtubeId: v.youtubeId,
      title: v.title,
      description: v.description,
      youtubeUrl: v.youtubeUrl,
      isShort: isShort(entry),
    })
  }

  // Newest first: RSS order is chronological-newest; data/videos.ts trails it.
  return Array.from(byId.values())
}

async function generateXCopy(
  target: SyndicationTarget,
  enrichment: Enrichment | null,
  groq: Groq,
): Promise<Omit<XSyndicationDraft, 'youtubeId' | 'videoTitle' | 'youtubeUrl' | 'isShort' | 'status' | 'generatedAt'>> {
  const format = target.isShort
    ? 'これはYouTube Shorts（短尺・縦型）です。launchPostは縦型動画にそのまま添える、短く強いフックにしてください。threadは2つで構いません。'
    : 'これは長尺インタビュー本編です。launchPostは本編の最も惹きつける問いを軸にしてください。'

  const enrichmentBlock = enrichment
    ? `\n\n参考（自動生成済みのエピソード分析）:\n要約: ${enrichment.summary}\nテーマ: ${enrichment.keyThemes.join('、')}\n印象的な言葉: ${enrichment.keyQuotes.join(' / ')}`
    : ''

  const completion = await groq.chat.completions.create({
    model: process.env.GROQ_MODEL ?? 'llama-3.3-70b-versatile',
    messages: [
      {
        role: 'user',
        content: `あなたは「The Curious Club（キュリクラ）」のSNS編集者です。
このチャンネルは現役医学生が、医療・ビジネス・社会など分野を超えて"熱を持って生きる人"にインタビューするプロジェクトです。
ゲストは理事長・院長・経営者・議員など実名の方々。**ゲストへの敬意と誠実さ**が最優先で、煽り・誇張・ゲストが恥ずかしく思う表現は禁止です。

これからX（旧Twitter）用の投稿コピーを作ります。前提:
- 動画は**ネイティブ動画としてXに直接アップ**する想定。本文(launchPost)にYouTubeリンクは入れない。
- YouTubeリンクはリプライ(linkReply)に入れる。
- ゲスト本人がリポストしたくなる文面にする。@メンションは後で人間が入れるため "（＠ゲスト）" のプレースホルダを残す。
- 日本語。各投稿は140字程度を目安に、長くても全角240字以内。

${format}

エピソード情報:
タイトル: ${target.title}
説明文: ${target.description}${enrichmentBlock}

以下のJSONスキーマに従い、有効なJSONのみを返してください（前置き不要）:
{
  "launchPost": "ネイティブ動画に添える本文（リンクなし、フック重視）",
  "linkReply": "YouTubeリンクを案内するリプライ文（リンク自体は {url} と書く）",
  "thread": ["「印象的だった話」スレッド（各ツイート）"],
  "quoteCard": { "quote": "名言カード用の一言", "attribution": "発言者名（敬称つき）" },
  "guestResharePost": "ゲスト本人がそのままリポスト/引用できる文面（＠ゲスト プレースホルダ込み）",
  "hashtags": ["#で始まるハッシュタグ（鹿児島や分野など、3つまで）"]
}`,
      },
    ],
    max_tokens: 2048,
    temperature: 0.7,
  })

  const content = completion.choices[0]?.message?.content ?? ''
  const parsed = JSON.parse(extractJson(content)) as {
    launchPost: string
    linkReply: string
    thread: string[]
    quoteCard: { quote: string; attribution: string }
    guestResharePost: string
    hashtags: string[]
  }

  return {
    ...parsed,
    linkReply: parsed.linkReply.replace('{url}', target.youtubeUrl),
    // Suggested location; reviewer drops the real .mp4 here (or clears it for text-only).
    mediaPath: `media/x/${target.youtubeId}.mp4`,
    reviewerNotes: [
      'ゲストの@ハンドルを「（＠ゲスト）」と置き換える',
      target.isShort ? '縦型Shortのmp4を添付' : '本編のハイライトmp4（1〜2分）を添付',
      '事実関係・敬称・所属をゲスト本人基準で確認',
    ],
  }
}

export async function loadQueue(queuePath = QUEUE_PATH): Promise<XQueue> {
  try {
    return JSON.parse(await readFile(queuePath, 'utf-8')) as XQueue
  } catch {
    return { updated: new Date().toISOString(), drafts: [] }
  }
}

async function saveQueue(queue: XQueue, queuePath = QUEUE_PATH) {
  await mkdir(path.dirname(queuePath), { recursive: true })
  queue.updated = new Date().toISOString()
  await writeFile(queuePath, `${JSON.stringify(queue, null, 2)}\n`, 'utf-8')
}

interface RunOptions {
  limit?: number
  id?: string
  all?: boolean
  force?: boolean
  queuePath?: string
  log?: Pick<Console, 'log' | 'error'>
  write?: (message: string) => void
}

export async function runXSyndicate(options: RunOptions = {}) {
  const log = options.log ?? console
  const write = options.write ?? ((m: string) => process.stdout.write(m))
  const queuePath = options.queuePath ?? QUEUE_PATH

  const targets = collectTargets(await fetchRssEntries())
  const queue = await loadQueue(queuePath)
  const queued = new Set(queue.drafts.map((d) => d.youtubeId))

  let candidates = targets
  if (options.id) candidates = candidates.filter((t) => t.youtubeId === options.id)
  if (!options.force) candidates = candidates.filter((t) => !queued.has(t.youtubeId))
  if (!options.all && !options.id) candidates = candidates.slice(0, options.limit ?? 3)

  if (candidates.length === 0) {
    log.log('OK: nothing to generate — queue is up to date (use --force to regenerate).')
    return { generated: 0, queued: queue.drafts.length, exitCode: 0 }
  }

  if (!process.env.GROQ_API_KEY) {
    log.error(`MISSING: GROQ_API_KEY is not set. Skipped ${candidates.length} draft(s).`)
    return { generated: 0, queued: queue.drafts.length, exitCode: 1 }
  }

  const groq = new Groq({ apiKey: process.env.GROQ_API_KEY })

  for (const target of candidates) {
    write(`Drafting X copy for ${target.youtubeId} ${target.title.slice(0, 48)}... `)
    const enrichment = await getEnrichment(target.youtubeId)
    const copy = await generateXCopy(target, enrichment, groq)
    const draft: XSyndicationDraft = {
      youtubeId: target.youtubeId,
      videoTitle: target.title,
      youtubeUrl: target.youtubeUrl,
      isShort: target.isShort,
      status: 'pending_review',
      generatedAt: new Date().toISOString(),
      ...copy,
    }
    const existingIdx = queue.drafts.findIndex((d) => d.youtubeId === target.youtubeId)
    if (existingIdx >= 0) queue.drafts[existingIdx] = draft
    else queue.drafts.unshift(draft)
    log.log('OK')
  }

  await saveQueue(queue, queuePath)
  log.log(`OK: wrote ${candidates.length} draft(s) to ${queuePath} (status: pending_review).`)
  return { generated: candidates.length, queued: queue.drafts.length, exitCode: 0 }
}

function parseArgs(argv: string[]): RunOptions {
  const opts: RunOptions = {}
  for (const arg of argv) {
    if (arg === '--all') opts.all = true
    else if (arg === '--force') opts.force = true
    else if (arg.startsWith('--limit=')) opts.limit = Number(arg.slice('--limit='.length))
    else if (arg.startsWith('--id=')) opts.id = arg.slice('--id='.length)
  }
  return opts
}

async function main() {
  loadEnvLocal()
  const result = await runXSyndicate(parseArgs(process.argv.slice(2)))
  if (result.exitCode !== 0) process.exit(result.exitCode)
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : error)
    process.exit(1)
  })
}
