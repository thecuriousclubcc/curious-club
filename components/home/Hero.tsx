'use client'

import Link from 'next/link'
import { useState } from 'react'
import { Volume2, VolumeX, ChevronLeft, ChevronRight } from 'lucide-react'
import { videos } from '@/data/videos'

export default function Hero() {
  const [current, setCurrent] = useState(0)
  const [muted, setMuted] = useState(true)

  const prev = () => setCurrent((i) => (i === 0 ? videos.length - 1 : i - 1))
  const next = () => setCurrent((i) => (i === videos.length - 1 ? 0 : i + 1))

  const video = videos[current]

  return (
    <section className="relative overflow-hidden min-h-[90vh] flex items-center">
      {/* YouTube background video */}
      <div className="absolute inset-0 w-full h-full pointer-events-none">
        <iframe
          key={video.youtubeId}
          src={`https://www.youtube.com/embed/${video.youtubeId}?autoplay=1&mute=${muted ? 1 : 0}&loop=1&playlist=${video.youtubeId}&controls=0&showinfo=0&rel=0&playsinline=1&modestbranding=1`}
          allow="autoplay; encrypted-media"
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"
          style={{ width: '177.78vh', height: '100vh', minWidth: '100%', minHeight: '56.25vw' }}
        />
      </div>

      {/* Dark overlay */}
      <div className="absolute inset-0 bg-black/60" />

      {/* Left arrow */}
      <button
        onClick={prev}
        className="absolute left-4 top-1/2 -translate-y-1/2 z-10 bg-black/40 hover:bg-black/70 text-white rounded-full p-2 transition-colors backdrop-blur-sm"
        aria-label="前の動画"
      >
        <ChevronLeft size={28} />
      </button>

      {/* Right arrow */}
      <button
        onClick={next}
        className="absolute right-4 top-1/2 -translate-y-1/2 z-10 bg-black/40 hover:bg-black/70 text-white rounded-full p-2 transition-colors backdrop-blur-sm"
        aria-label="次の動画"
      >
        <ChevronRight size={28} />
      </button>

      {/* Content */}
      <div className="relative z-10 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-28 md:py-44 w-full">
        <div className="max-w-3xl">
          <p className="text-teal-400 text-xs font-medium tracking-widest uppercase mb-6">
            The Curious Club — キュリクラ
          </p>
          <h1 className="text-5xl md:text-7xl font-bold text-white leading-tight tracking-tight">
            好奇心で、
            <br />
            世界をひらく。
          </h1>
          <p className="mt-7 text-lg md:text-xl text-slate-200 leading-relaxed max-w-2xl">
            医療と社会のリアルを、会話で届ける。
            <br className="hidden sm:block" />
            台本なしの対談から生まれる、学びと熱量のチャンネル。
          </p>
          <div className="mt-10 flex flex-col sm:flex-row gap-4">
            <a
              href="https://www.youtube.com/@TheCuriousClub_CC"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-2 bg-teal-600 text-white px-8 py-4 rounded-full text-sm font-semibold hover:bg-teal-500 transition-colors shadow-sm"
            >
              最新動画を見る
            </a>
            <Link
              href="/contact"
              className="inline-flex items-center justify-center gap-2 border border-white/50 text-white px-8 py-4 rounded-full text-sm font-semibold hover:border-white hover:bg-white/10 transition-colors"
            >
              出演・取材の相談をする
            </Link>
          </div>
        </div>
      </div>

      {/* Bottom bar: dots + current video title + mute */}
      <div className="absolute bottom-0 left-0 right-0 z-10 px-6 py-4 bg-gradient-to-t from-black/70 to-transparent flex items-center justify-between gap-4">
        {/* Dots */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {videos.map((_, i) => (
            <button
              key={i}
              onClick={() => setCurrent(i)}
              className={`rounded-full transition-all ${
                i === current ? 'bg-white w-4 h-2' : 'bg-white/40 w-2 h-2 hover:bg-white/70'
              }`}
              aria-label={`動画 ${i + 1}`}
            />
          ))}
        </div>

        {/* Current video title */}
        <p className="text-white/80 text-xs truncate max-w-xs hidden sm:block">
          {video.title}
        </p>

        {/* Mute button */}
        <button
          onClick={() => setMuted(!muted)}
          className="flex items-center gap-2 bg-black/50 hover:bg-black/70 text-white text-xs px-4 py-2 rounded-full transition-colors backdrop-blur-sm flex-shrink-0"
          aria-label={muted ? '音声をオンにする' : '音声をオフにする'}
        >
          {muted ? <VolumeX size={14} /> : <Volume2 size={14} />}
          {muted ? '音声をオン' : '音声をオフ'}
        </button>
      </div>
    </section>
  )
}
