import type { MetadataRoute } from 'next'
import { getAllVideos } from '@/lib/videos'
import { SITE_URL } from '@/lib/site'

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticPages: MetadataRoute.Sitemap = [
    {
      url: SITE_URL,
      lastModified: new Date(),
      changeFrequency: 'weekly',
      priority: 1,
    },
    {
      url: `${SITE_URL}/videos`,
      lastModified: new Date(),
      changeFrequency: 'weekly',
      priority: 0.9,
    },
    {
      url: `${SITE_URL}/about`,
      lastModified: new Date(),
      changeFrequency: 'monthly',
      priority: 0.7,
    },
    {
      url: `${SITE_URL}/contact`,
      lastModified: new Date(),
      changeFrequency: 'monthly',
      priority: 0.6,
    },
  ]

  const videos = await getAllVideos()
  const episodePages: MetadataRoute.Sitemap = videos.map((v) => ({
    url: `${SITE_URL}/videos/${v.youtubeId}`,
    lastModified: new Date(v.publishedAt),
    changeFrequency: 'monthly',
    priority: 0.8,
  }))

  return [...staticPages, ...episodePages]
}
