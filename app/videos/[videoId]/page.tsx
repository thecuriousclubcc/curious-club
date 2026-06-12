import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import Image from 'next/image'
import Link from 'next/link'
import { videos as staticVideos } from '@/data/videos'
import { getChannelVideos } from '@/lib/youtube'
import { getEnrichment } from '@/lib/enrichment'
import EpisodeSummary from '@/components/videos/EpisodeSummary'
import CareerInsights from '@/components/videos/CareerInsights'
import { ExternalLink, ArrowLeft } from 'lucide-react'

export const revalidate = 3600

const CHANNEL_ID = process.env.YOUTUBE_CHANNEL_ID ?? ''

async function getAllVideos() {
  const liveVideos = CHANNEL_ID ? await getChannelVideos(CHANNEL_ID).catch(() => []) : []
  return liveVideos.length > 0 ? liveVideos : staticVideos
}

export async function generateStaticParams() {
  const videos = await getAllVideos()
  return videos.map((v) => ({ videoId: v.youtubeId }))
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ videoId: string }>
}): Promise<Metadata> {
  const { videoId } = await params
  const videos = await getAllVideos()
  const video = videos.find((v) => v.youtubeId === videoId)
  if (!video) return {}

  return {
    title: video.title,
    description: video.description.slice(0, 160),
    openGraph: {
      title: video.title,
      description: video.description.slice(0, 160),
      type: 'video.episode',
      images: [{ url: video.thumbnailUrl, width: 1280, height: 720, alt: video.title }],
    },
    twitter: {
      card: 'summary_large_image',
      title: video.title,
      description: video.description.slice(0, 160),
      images: [video.thumbnailUrl],
    },
  }
}

export default async function EpisodePage({
  params,
}: {
  params: Promise<{ videoId: string }>
}) {
  const { videoId } = await params
  const videos = await getAllVideos()
  const video = videos.find((v) => v.youtubeId === videoId)
  if (!video) notFound()

  const enrichment = await getEnrichment(videoId)

  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'VideoObject',
    name: video.title,
    description: video.description,
    thumbnailUrl: video.thumbnailUrl,
    uploadDate: video.publishedAt,
    contentUrl: video.youtubeUrl,
    embedUrl: `https://www.youtube.com/embed/${videoId}`,
    publisher: {
      '@type': 'Organization',
      name: 'The Curious Club（キュリクラ）',
      url: 'https://curious-club.jp',
    },
  }

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <div className="min-h-screen bg-slate-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          {/* Back */}
          <Link
            href="/videos"
            className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-teal-700 transition-colors mb-8"
          >
            <ArrowLeft size={14} />
            動画一覧へ
          </Link>

          {/* Tags */}
          <div className="flex gap-2 flex-wrap mb-4">
            {video.tags.map((tag) => (
              <span key={tag} className="text-xs text-teal-700 bg-teal-50 px-3 py-1 rounded-full">
                {tag}
              </span>
            ))}
          </div>

          {/* Title */}
          <h1 className="text-2xl md:text-3xl font-bold text-slate-900 leading-snug mb-3">
            {video.title}
          </h1>
          <p className="text-sm text-slate-400 mb-8">
            {new Date(video.publishedAt).toLocaleDateString('ja-JP', {
              year: 'numeric',
              month: 'long',
              day: 'numeric',
            })}
            {video.viewCount && ` · ${Number(video.viewCount).toLocaleString('ja-JP')} 回視聴`}
          </p>

          {/* YouTube Embed */}
          <div className="relative w-full aspect-video rounded-2xl overflow-hidden shadow-lg mb-10 bg-black">
            <iframe
              src={`https://www.youtube.com/embed/${videoId}`}
              title={video.title}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              className="absolute inset-0 w-full h-full"
            />
          </div>

          {/* Description */}
          <p className="text-slate-600 text-sm leading-relaxed mb-10 whitespace-pre-line">
            {video.description}
          </p>

          {/* AI Enrichment */}
          {enrichment && (
            <div className="space-y-6">
              <EpisodeSummary enrichment={enrichment} />
              <CareerInsights insights={enrichment.careerInsights} />
            </div>
          )}

          {/* YouTube link */}
          <div className="mt-12 pt-8 border-t border-slate-100 flex justify-center">
            <a
              href={video.youtubeUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 bg-teal-700 text-white px-8 py-4 rounded-full text-sm font-semibold hover:bg-teal-800 transition-colors"
            >
              YouTubeで見る
              <ExternalLink size={14} />
            </a>
          </div>
        </div>
      </div>
    </>
  )
}
