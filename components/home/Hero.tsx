import Link from 'next/link'

export default function Hero() {
  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-slate-50 to-white">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-28 md:py-44">
        <div className="max-w-3xl">
          <p className="text-teal-700 text-xs font-medium tracking-widest uppercase mb-6">
            The Curious Club — キュリクラ
          </p>
          <h1 className="text-5xl md:text-7xl font-bold text-slate-900 leading-tight tracking-tight">
            好奇心で、
            <br />
            世界をひらく。
          </h1>
          <p className="mt-7 text-lg md:text-xl text-slate-600 leading-relaxed max-w-2xl">
            医療と社会のリアルを、会話で届ける。
            <br className="hidden sm:block" />
            台本なしの対談から生まれる、学びと熱量のチャンネル。
          </p>
          <div className="mt-10 flex flex-col sm:flex-row gap-4">
            <a
              href="https://www.youtube.com/@TheCuriousClub_CC"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-2 bg-teal-700 text-white px-8 py-4 rounded-full text-sm font-semibold hover:bg-teal-800 transition-colors shadow-sm"
            >
              最新動画を見る
            </a>
            <Link
              href="/contact"
              className="inline-flex items-center justify-center gap-2 border border-slate-300 text-slate-700 px-8 py-4 rounded-full text-sm font-semibold hover:border-teal-600 hover:text-teal-700 transition-colors"
            >
              出演・取材の相談をする
            </Link>
          </div>
        </div>
      </div>

      {/* Decorative gradient */}
      <div
        aria-hidden="true"
        className="absolute top-0 right-0 w-1/2 h-full pointer-events-none"
        style={{
          background:
            'radial-gradient(circle at 80% 40%, rgba(13,148,136,0.06) 0%, transparent 65%)',
        }}
      />
    </section>
  )
}
