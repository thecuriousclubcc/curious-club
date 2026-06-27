// Single source of truth for episode data.
//
// Resolution order:
//   1. YouTube Data API (when YOUTUBE_API_KEY is set) — full history + stats
//   2. YouTube RSS feed — free, no API key, returns the latest ~15 uploads
//   3. Static data/videos.ts — always available fallback
//
// Remote data is merged over the static list: curated entries keep their
// titles/descriptions/tags/featured flags, remote contributes view counts
// and any episodes published after the last static entry. Shorts are
// excluded everywhere.

import { videos as staticVideos, type Video } from '@/data/videos'
import { getChannelVideos } from '@/lib/youtube'

export type { Video }

const CHANNEL_ID = process.env.YOUTUBE_CHANNEL_ID || 'UCtMsMejHNPL_PGVv_iJ2xNw'
const RSS_URL = `https://www.youtube.com/feeds/videos.xml?channel_id=${CHANNEL_ID}`

interface RemoteEntry {
  youtubeId: string
  title: string
  description: string
  publishedAt: string
  viewCount?: string
  duration?: string
}

function parseRssEntries(xml: string): RemoteEntry[] {
  const entries: RemoteEntry[] = []
  const entryBlocks = xml.match(/<entry>[\s\S]*?<\/entry>/g) ?? []

  for (const block of entryBlocks) {
    const youtubeId = block.match(/<yt:videoId>([^<]+)<\/yt:videoId>/)?.[1]
    const title = block.match(/<media:title>([\s\S]*?)<\/media:title>/)?.[1]
    if (!youtubeId || !title) continue

    const description =
      block.match(/<media:description>([\s\S]*?)<\/media:description>/)?.[1] ?? ''
    const publishedAt = block.match(/<published>([^<]+)<\/published>/)?.[1] ?? ''
    const viewCount = block.match(/<media:statistics views="(\d+)"/)?.[1]

    entries.push({
      youtubeId,
      title: decodeXmlEntities(title),
      description: decodeXmlEntities(description),
      publishedAt: publishedAt.slice(0, 10),
      viewCount,
    })
  }

  return entries
}

function decodeXmlEntities(s: string): string {
  return s
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
}

function isShort(entry: RemoteEntry): boolean {
  // YouTube RSS has no duration and its alternate links are watch URLs, so the
  // free RSS path relies on creator hashtag tagging.
  return /#(?:shorts?|ショート)(?:$|[\s.,!?:;)\]}。、！？])/i.test(
    `${entry.title}\n${entry.description}`,
  )
}

async function getRssEntries(): Promise<RemoteEntry[]> {
  const res = await fetch(RSS_URL, { next: { revalidate: 3600 } })
  if (!res.ok) throw new Error(`YouTube RSS error: ${res.status}`)
  return parseRssEntries(await res.text())
}

/**
 * Merge remote data over the curated static list: static entries keep their
 * curated fields but pick up live stats; new full-length episodes are
 * appended in publication order.
 */
function mergeWithStatic(remote: RemoteEntry[]): Video[] {
  const staticIds = new Set(staticVideos.map((v) => v.youtubeId))

  const merged: Video[] = staticVideos.map((v) => {
    const r = remote.find((e) => e.youtubeId === v.youtubeId)
    if (!r) return v
    return {
      ...v,
      viewCount: r.viewCount ?? v.viewCount,
      duration: r.duration ?? v.duration,
    }
  })

  const newEpisodes = remote
    .filter((e) => !staticIds.has(e.youtubeId) && !isShort(e))
    .sort((a, b) => a.publishedAt.localeCompare(b.publishedAt))

  for (const e of newEpisodes) {
    merged.push({
      id: e.youtubeId,
      youtubeId: e.youtubeId,
      title: e.title,
      description: e.description,
      thumbnailUrl: `https://img.youtube.com/vi/${e.youtubeId}/maxresdefault.jpg`,
      youtubeUrl: `https://www.youtube.com/watch?v=${e.youtubeId}`,
      publishedAt: e.publishedAt,
      featured: false,
      tags: [],
      viewCount: e.viewCount,
      duration: e.duration,
    })
  }

  return merged
}

export async function getAllVideos(): Promise<Video[]> {
  // 1. YouTube Data API when configured
  if (process.env.YOUTUBE_API_KEY) {
    const liveVideos = await getChannelVideos(CHANNEL_ID).catch(() => [])
    if (liveVideos.length > 0) {
      return mergeWithStatic(
        liveVideos.map((v) => ({
          youtubeId: v.youtubeId,
          title: v.title,
          description: v.description,
          publishedAt: v.publishedAt,
          viewCount: v.viewCount,
          duration: v.duration,
        })),
      )
    }
  }

  // 2. RSS feed (free, no key)
  try {
    const rssEntries = await getRssEntries()
    if (rssEntries.length > 0) return mergeWithStatic(rssEntries)
  } catch {
    // network error / feed unavailable — fall through
  }

  // 3. Static fallback
  return staticVideos
}

export async function getFeaturedVideos(): Promise<Video[]> {
  const videos = await getAllVideos()
  const featured = videos.filter((v) => v.featured)
  // Fall back to the three most recent episodes if nothing is flagged
  return featured.length > 0 ? featured : videos.slice(-3).reverse()
}
