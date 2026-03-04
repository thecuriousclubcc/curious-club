import Image from 'next/image'
import type { Video } from '@/data/videos'

interface VideoCardProps {
  video: Video
}

export default function VideoCard({ video }: VideoCardProps) {
  return (
    <a
      href={video.youtubeUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="group block bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-md transition-all duration-300 border border-slate-100"
    >
      <div className="relative aspect-video overflow-hidden bg-slate-100">
        <Image
          src={video.thumbnailUrl}
          alt={video.title}
          fill
          className="object-cover group-hover:scale-105 transition-transform duration-500"
        />
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-12 h-12 rounded-full bg-white/90 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity shadow">
            <svg
              viewBox="0 0 24 24"
              fill="currentColor"
              className="w-5 h-5 text-teal-700 ml-0.5"
            >
              <path d="M8 5v14l11-7z" />
            </svg>
          </div>
        </div>
      </div>
      <div className="p-5">
        <div className="flex gap-2 flex-wrap mb-3">
          {video.tags.slice(0, 3).map((tag) => (
            <span key={tag} className="text-xs text-teal-700 bg-teal-50 px-2 py-1 rounded-full">
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
  )
}
