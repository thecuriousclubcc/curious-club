import type { Video } from '../data/videos'

export const DEFAULT_CHANNEL_ID = 'UCtMsMejHNPL_PGVv_iJ2xNw'

export interface RssVideoEntry {
  youtubeId: string
  title: string
  description: string
  publishedAt: string
  link: string
  viewCount?: string
}

export function youtubeRssUrl(channelId = DEFAULT_CHANNEL_ID): string {
  return `https://www.youtube.com/feeds/videos.xml?channel_id=${channelId}`
}

export function decodeXmlEntities(value: string): string {
  return value
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&#(\d+);/g, (_match, code: string) => String.fromCodePoint(Number(code)))
    .replace(/&#x([0-9a-f]+);/gi, (_match, code: string) =>
      String.fromCodePoint(Number.parseInt(code, 16)),
    )
}

export function parseRssEntries(xml: string): RssVideoEntry[] {
  const entryBlocks = xml.match(/<entry>[\s\S]*?<\/entry>/g) ?? []

  return entryBlocks.flatMap((block) => {
    const youtubeId = block.match(/<yt:videoId>([^<]+)<\/yt:videoId>/)?.[1]
    const title =
      block.match(/<media:title>([\s\S]*?)<\/media:title>/)?.[1] ??
      block.match(/<title>([\s\S]*?)<\/title>/)?.[1]

    if (!youtubeId || !title) return []

    const description =
      block.match(/<media:description>([\s\S]*?)<\/media:description>/)?.[1] ?? ''
    const publishedAt = block.match(/<published>([^<]+)<\/published>/)?.[1] ?? ''
    const viewCount = block.match(/<media:statistics views="(\d+)"/)?.[1]
    const link = block.match(/<link rel="alternate" href="([^"]+)"/)?.[1] ?? ''

    return [
      {
        youtubeId,
        title: decodeXmlEntities(title),
        description: decodeXmlEntities(description),
        publishedAt: publishedAt.slice(0, 10),
        link: decodeXmlEntities(link),
        viewCount,
      },
    ]
  })
}

export function isShort(entry: Pick<RssVideoEntry, 'title' | 'description'>) {
  // YouTube channel RSS does not include duration and uses watch URLs for Shorts,
  // so the free RSS path relies on creator hashtag tagging.
  return /#(?:shorts?|ショート)(?:$|[\s.,!?:;)\]}。、！？])/i.test(
    `${entry.title}\n${entry.description}`,
  )
}

export function findNewLongFormEntries(
  entries: RssVideoEntry[],
  existingVideos: Pick<Video, 'youtubeId'>[],
): RssVideoEntry[] {
  const existingIds = new Set(existingVideos.map((video) => video.youtubeId))

  return entries
    .filter((entry) => !existingIds.has(entry.youtubeId))
    .filter((entry) => !isShort(entry))
    .sort((a, b) => a.publishedAt.localeCompare(b.publishedAt))
}

export function nextVideoId(existingVideos: Pick<Video, 'id'>[], offset = 0): string {
  const numericIds = existingVideos
    .map((video) => Number(video.id))
    .filter((id) => Number.isInteger(id) && id > 0)

  if (numericIds.length !== existingVideos.length) return ''
  return String(Math.max(0, ...numericIds) + offset + 1)
}

export function videoFromRssEntry(
  entry: RssVideoEntry,
  existingVideos: Pick<Video, 'id'>[],
  offset = 0,
): Video {
  return {
    id: nextVideoId(existingVideos, offset) || entry.youtubeId,
    youtubeId: entry.youtubeId,
    title: entry.title,
    description: entry.description,
    thumbnailUrl: `https://img.youtube.com/vi/${entry.youtubeId}/maxresdefault.jpg`,
    youtubeUrl: `https://www.youtube.com/watch?v=${entry.youtubeId}`,
    publishedAt: entry.publishedAt,
    featured: false,
    tags: [],
    viewCount: entry.viewCount,
  }
}

function tsString(value: string): string {
  if (value.includes('\n')) {
    return `\`${value.replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\$\{/g, '\\${')}\``
  }

  return `'${value.replace(/\\/g, '\\\\').replace(/'/g, "\\'")}'`
}

export function renderVideoObject(video: Video): string {
  const optionalLines = [
    video.viewCount ? `    viewCount: ${tsString(video.viewCount)},` : '',
    video.duration ? `    duration: ${tsString(video.duration)},` : '',
  ].filter(Boolean)

  return [
    '  {',
    `    id: ${tsString(video.id)},`,
    `    youtubeId: ${tsString(video.youtubeId)},`,
    `    title: ${tsString(video.title)},`,
    `    description: ${tsString(video.description)},`,
    `    thumbnailUrl: ${tsString(video.thumbnailUrl)},`,
    `    youtubeUrl: ${tsString(video.youtubeUrl)},`,
    `    publishedAt: ${tsString(video.publishedAt)},`,
    '    featured: false,',
    '    tags: [],',
    ...optionalLines,
    '  },',
  ].join('\n')
}

export function appendVideosToDataFile(source: string, videosToAppend: Video[]): string {
  if (videosToAppend.length === 0) return source

  const marker = /\n]\s*\n+export const featuredVideos/
  const match = marker.exec(source)
  if (!match) {
    throw new Error('Could not find the videos array closing marker in data/videos.ts')
  }

  const insertion = `\n${videosToAppend.map(renderVideoObject).join('\n')}`
  return `${source.slice(0, match.index)}${insertion}${source.slice(match.index)}`
}
