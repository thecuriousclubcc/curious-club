import type { Metadata } from 'next'
import BrainSearch from '@/components/brain/BrainSearch'

export const metadata: Metadata = {
  title: '動画内検索',
  description:
    'The Curious Club（キュリクラ）の全動画の発言を横断検索。誰が・どの動画の・何分何秒に話したかを見つけて、その場面から再生できます。',
}

export default function BrainPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="mb-10">
          <p className="text-teal-700 text-xs font-medium tracking-widest uppercase mb-3">
            Search Inside Videos
          </p>
          <h1 className="text-3xl md:text-4xl font-bold text-slate-900">動画内検索</h1>
          <p className="mt-4 text-slate-600 leading-relaxed max-w-xl text-sm">
            全エピソードの「発言そのもの」を横断検索。
            誰が・どの動画の・何分何秒に話したかが見つかり、その場面からすぐ再生できます。
          </p>
        </div>
        <BrainSearch />
      </div>
    </div>
  )
}
