import Link from 'next/link'

export default function CTASection() {
  return (
    <section className="py-28 bg-teal-900">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <h2 className="text-3xl md:text-4xl font-bold text-white leading-tight">
          一緒に、面白い会話を
          <br className="hidden sm:block" />
          つくりませんか。
        </h2>
        <p className="mt-6 text-teal-200 text-base md:text-lg leading-relaxed max-w-xl mx-auto">
          出演依頼・取材依頼・メディアコラボレーション・その他お仕事のご相談など、
          お気軽にお問い合わせください。
        </p>
        <div className="mt-10 flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            href="/contact"
            className="inline-flex items-center justify-center bg-white text-teal-900 px-8 py-4 rounded-full text-sm font-semibold hover:bg-teal-50 transition-colors"
          >
            出演・取材の相談をする
          </Link>
          <a
            href="https://www.youtube.com/@TheCuriousClub_CC"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center border border-teal-700 text-teal-100 px-8 py-4 rounded-full text-sm font-semibold hover:border-teal-500 hover:text-white transition-colors"
          >
            チャンネルを見る
          </a>
        </div>
      </div>
    </section>
  )
}
