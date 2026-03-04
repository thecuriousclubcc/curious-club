import type { Metadata } from 'next'
import { videos } from '@/data/videos'
import VideoCard from '@/components/videos/VideoCard'

export const metadata: Metadata = {
  title: '動画一覧',
  description:
    'The Curious Club（キュリクラ）の全動画一覧。医療と社会をテーマにした対談・インタビュー動画をご覧いただけます。',
}

export default function VideosPage() {
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
            <br />
            各動画のサムネイルをクリックすると、YouTubeへ移動します。
          </p>
        </div>

        {/* Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {videos.map((video) => (
            <VideoCard key={video.id} video={video} />
          ))}
        </div>

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
