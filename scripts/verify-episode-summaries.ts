import { existsSync, readFileSync } from 'fs'
import path from 'path'
import { videos } from '../data/videos'
import {
  findNewLongFormEntries,
  isShort,
  parseRssEntries,
  youtubeRssUrl,
} from './episode-enricher-core'

async function fetchRssEntries() {
  const res = await fetch(youtubeRssUrl(process.env.YOUTUBE_CHANNEL_ID), { cache: 'no-store' })
  if (!res.ok) throw new Error(`YouTube RSS returned ${res.status}`)
  return parseRssEntries(await res.text())
}

function hasSummary(videoId: string): boolean {
  const enrichmentPath = path.join(process.cwd(), 'public', 'data', 'enrichments', `${videoId}.json`)
  if (!existsSync(enrichmentPath)) return false

  try {
    const parsed = JSON.parse(readFileSync(enrichmentPath, 'utf-8')) as { summary?: unknown }
    return typeof parsed.summary === 'string' && parsed.summary.trim().length > 0
  } catch {
    return false
  }
}

async function main() {
  const rssEntries = await fetchRssEntries()
  const unexpectedNewEntries = findNewLongFormEntries(rssEntries, videos)
  const staticMissingSummaries = videos.filter((video) => !hasSummary(video.youtubeId))
  const rssKnownLongForm = rssEntries.filter((entry) => !isShort(entry))
  const rssMissingSummaries = rssKnownLongForm
    .filter((entry) => videos.some((video) => video.youtubeId === entry.youtubeId))
    .filter((entry) => !hasSummary(entry.youtubeId))

  if (
    unexpectedNewEntries.length === 0 &&
    staticMissingSummaries.length === 0 &&
    rssMissingSummaries.length === 0
  ) {
    console.log(
      `OK: ${videos.length} data/videos.ts episode(s) have summaries; ${rssKnownLongForm.length} current RSS long-form episode(s) are present and summarized.`,
    )
    return
  }

  console.log('MISSING: episode summary verification failed.')

  for (const entry of unexpectedNewEntries) {
    console.log(`MISSING data/videos.ts: ${entry.youtubeId} ${entry.title}`)
  }

  for (const video of staticMissingSummaries) {
    console.log(`MISSING summary: ${video.youtubeId} ${video.title}`)
  }

  for (const entry of rssMissingSummaries) {
    console.log(`MISSING RSS summary: ${entry.youtubeId} ${entry.title}`)
  }

  process.exit(1)
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error)
  process.exit(1)
})
