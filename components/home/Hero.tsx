'use client'

import Link from 'next/link'
import { useState } from 'react'
import { Volume2, VolumeX } from 'lucide-react'

export default function Hero() {
  const [muted, setMuted] = useState(true)

  return (
    <section className="relative overflow-hidden min-h-[90vh] flex items-center">
      {/* YouTube background video */}
      <div className="absolute inset-0 w-full h-full pointer-events-none">
        <iframe
          src={`https://www.youtube.com/embed/wyjwFxkeOGc?autoplay=1&mute=${muted ? 1 : 0}&loop=1&playlist=wyjwFxkeOGc&controls=0&showinfo=0&rel=0&playsinline=1&modestbranding=1`}
          allow="autoplay; encrypted-media"
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"
          style={{ width: '177.78vh', height: '100vh', minWidth: '100%', minHeight: '56.25vw' }}
        />
      </div>

      {/* Dark overlay for readability */}
      <div className="absolute inset-0 bg-black/60" />

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

      {/* Mute/unmute button */}
      <button
        onClick={() => setMuted(!muted)}
        className="absolute bottom-6 right-6 z-10 flex items-center gap-2 bg-black/50 hover:bg-black/70 text-white text-xs px-4 py-2 rounded-full transition-colors backdrop-blur-sm"
        aria-label={muted ? '音声をオンにする' : '音声をオフにする'}
      >
        {muted ? <VolumeX size={14} /> : <Volume2 size={14} />}
        {muted ? '音声をオン' : '音声をオフ'}
      </button>
    </section>
  )
}
