// YouTube Data API v3 wrapper — fetches channel uploads with view counts and duration.
// Falls back to static data/videos.ts when YOUTUBE_API_KEY is not set.

export interface YouTubeVideo {
  id: string
  youtubeId: string
  title: string
  description: string
  thumbnailUrl: string
  youtubeUrl: string
  publishedAt: string
  featured: boolean
  tags: string[]
  viewCount?: string
  duration?: string
}

const YOUTUBE_API_BASE = 'https://www.googleapis.com/youtube/v3'

async function fetchPlaylistItems(playlistId: string, apiKey: string): Promise<string[]> {
  const videoIds: string[] = []
  let pageToken: string | undefined

  do {
    const params = new URLSearchParams({
      part: 'contentDetails',
      playlistId,
      maxResults: '50',
      key: apiKey,
      ...(pageToken ? { pageToken } : {}),
    })
    const res = await fetch(`${YOUTUBE_API_BASE}/playlistItems?${params}`, {
      next: { revalidate: 3600 },
    })
    if (!res.ok) throw new Error(`YouTube playlistItems error: ${res.status}`)
    const data = await res.json()
    for (const item of data.items ?? []) {
      videoIds.push(item.contentDetails.videoId)
    }
    pageToken = data.nextPageToken
  } while (pageToken)

  return videoIds
}

async function fetchVideoDetails(
  videoIds: string[],
  apiKey: string,
): Promise<YouTubeVideo[]> {
  const results: YouTubeVideo[] = []

  for (let i = 0; i < videoIds.length; i += 50) {
    const chunk = videoIds.slice(i, i + 50)
    const params = new URLSearchParams({
      part: 'snippet,statistics,contentDetails',
      id: chunk.join(','),
      key: apiKey,
    })
    const res = await fetch(`${YOUTUBE_API_BASE}/videos?${params}`, {
      next: { revalidate: 3600 },
    })
    if (!res.ok) throw new Error(`YouTube videos error: ${res.status}`)
    const data = await res.json()

    for (const item of data.items ?? []) {
      const snippet = item.snippet
      results.push({
        id: item.id,
        youtubeId: item.id,
        title: snippet.title,
        description: snippet.description,
        thumbnailUrl:
          snippet.thumbnails?.maxres?.url ??
          snippet.thumbnails?.high?.url ??
          `https://img.youtube.com/vi/${item.id}/maxresdefault.jpg`,
        youtubeUrl: `https://www.youtube.com/watch?v=${item.id}`,
        publishedAt: snippet.publishedAt?.slice(0, 10) ?? '',
        featured: false,
        tags: snippet.tags?.slice(0, 5) ?? [],
        viewCount: item.statistics?.viewCount,
        duration: item.contentDetails?.duration,
      })
    }
  }

  return results
}

export async function getChannelVideos(channelId: string): Promise<YouTubeVideo[]> {
  const apiKey = process.env.YOUTUBE_API_KEY
  if (!apiKey) return []

  // The uploads playlist ID is always 'UC' replaced by 'UU' in the channel ID
  const uploadsPlaylistId = channelId.replace(/^UC/, 'UU')
  const videoIds = await fetchPlaylistItems(uploadsPlaylistId, apiKey)
  return fetchVideoDetails(videoIds, apiKey)
}
