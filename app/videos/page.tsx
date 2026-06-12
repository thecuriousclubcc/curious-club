import type { Metadata } from 'next'
import { videos as staticVideos } from '@/data/videos'
import { getChannelVideos } from '@/lib/youtube'
import VideoSearchBar from '@/components/videos/VideoSearchBar'

export const revalidate = 3600

export const metadata: Metadata = {
  title: '動画一覧',
  description:
    'The Curious Club（キュリクラ）の全動画一覧。分野を超えて"熱を持って生きる人"に迫った対話型インタビューをご覧いただけます。',
}

// Set your channel ID and YOUTUBE_API_KEY in .env.local to enable live data
const CHANNEL_ID = process.env.YOUTUBE_CHANNEL_ID ?? ''

export default async function VideosPage() {
  const liveVideos = CHANNEL_ID ? await getChannelVideos(CHANNEL_ID).catch(() => []) : []
  const videos = liveVideos.length > 0 ? liveVideos : staticVideos

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        {/* Header */}
        <div className="mb-12">
          <p className="text-teal-700 text-xs font-medium tracking-widest uppercase mb-3">
            Videos
          </p>
          <h1 className="text-3xl md:text-4xl font-bold text-slate-900">動画一覧</h1>
          <p className="mt-4 text-slate-600 leading-relaxed max-w-xl text-sm">
            すべての対談・インタビュー動画をご覧いただけます。
          </p>
        </div>

        {/* Search + filtered grid */}
        <VideoSearchBar videos={videos} />

        {/* CTA */}
        <div className="mt-16 text-center">
          <a
            href="https://www.youtube.com/@TheCuriousClub_CC"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 bg-teal-700 text-white px-8 py-4 rounded-full text-sm font-semibold hover:bg-teal-800 transition-colors"
          >
            YouTubeチャンネルをすべて見る
          </a>
        </div>
      </div>
    </div>
  )
}
