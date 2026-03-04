import Link from 'next/link'
import Image from 'next/image'
import { featuredVideos } from '@/data/videos'

export default function FeaturedVideos() {
  return (
    <section className="py-24 bg-slate-50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-end justify-between mb-12">
          <div>
            <p className="text-teal-700 text-xs font-medium tracking-widest uppercase mb-3">
              Featured Videos
            </p>
            <h2 className="text-3xl md:text-4xl font-bold text-slate-900">おすすめ動画</h2>
          </div>
          <Link
            href="/videos"
            className="text-sm text-teal-700 hover:text-teal-900 font-medium underline underline-offset-4 hidden sm:block transition-colors"
          >
            すべて見る →
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {featuredVideos.map((video) => (
            <a
              key={video.id}
              href={video.youtubeUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="group block bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-md transition-all duration-300"
            >
              <div className="relative aspect-video overflow-hidden bg-slate-100">
                <Image
                  src={video.thumbnailUrl}
                  alt={video.title}
                  fill
                  className="object-cover group-hover:scale-105 transition-transform duration-500"
                />
                {/* Play button overlay */}
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="w-14 h-14 rounded-full bg-white/90 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity shadow-lg">
                    <svg
                      viewBox="0 0 24 24"
                      fill="currentColor"
                      className="w-6 h-6 text-teal-700 ml-1"
                    >
                      <path d="M8 5v14l11-7z" />
                    </svg>
                  </div>
                </div>
              </div>
              <div className="p-5">
                <div className="flex gap-2 flex-wrap mb-3">
                  {video.tags.slice(0, 2).map((tag) => (
                    <span
                      key={tag}
                      className="text-xs text-teal-700 bg-teal-50 px-2 py-1 rounded-full"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
                <h3 className="text-sm font-semibold text-slate-900 leading-snug group-hover:text-teal-700 transition-colors">
                  {video.title}
                </h3>
                <p className="mt-2 text-xs text-slate-500 leading-relaxed line-clamp-2">
                  {video.description}
                </p>
                <p className="mt-3 text-xs text-slate-400">
                  {new Date(video.publishedAt).toLocaleDateString('ja-JP', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                  })}
                </p>
              </div>
            </a>
          ))}
        </div>

        <div className="mt-8 text-center sm:hidden">
          <Link
            href="/videos"
            className="text-sm text-teal-700 font-medium underline underline-offset-4"
          >
            すべての動画を見る →
          </Link>
        </div>
      </div>
    </section>
  )
}
