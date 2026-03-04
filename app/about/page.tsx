import type { Metadata } from 'next'
import Image from 'next/image'
import Link from 'next/link'

export const metadata: Metadata = {
  title: 'About',
  description:
    'The Curious Club（キュリクラ）について。チャンネルの活動内容、価値観、運営者情報、出演・取材依頼の流れをご紹介します。',
}

const achievements = [
  { label: '総動画数', value: '60+', unit: '本' },
  { label: '出演ゲスト', value: '13', unit: '名' },
  { label: '開始', value: '2025', unit: '年' },
]

const values = [
  {
    title: '台本なしの会話',
    body: '事前に話す内容を決めすぎません。その場で生まれる問いや気づきが、番組の核心だと考えているからです。',
  },
  {
    title: '医療の「リアル」を届ける',
    body: '美化せず、難しくもせず。現場にいる人の言葉で、医療と社会のリアルを丁寧に届けます。',
  },
  {
    title: '多様な視点の交差',
    body: '医師だけでなく、看護師・薬剤師・患者・研究者・医療経営者など、様々な立場のゲストをお招きします。',
  },
  {
    title: '誠実さを最優先に',
    body: '伝えることへの誠実さ、ゲストへの敬意、視聴者との信頼関係。これらを常に最優先にしています。',
  },
]

const requestSteps = [
  {
    step: '01',
    title: 'お問い合わせ',
    description:
      'お問い合わせフォームより、ご依頼の概要・ご要望をお送りください。',
  },
  {
    step: '02',
    title: 'ご連絡・ヒアリング',
    description:
      '内容を確認後、3営業日以内にご返信します。詳細なヒアリングを経て、方向性を確認します。',
  },
  {
    step: '03',
    title: '内容確認・日程調整',
    description:
      '企画内容・出演条件・撮影日程などを調整し、合意のうえ進行します。',
  },
  {
    step: '04',
    title: '収録・公開',
    description:
      '台本なしの自然な会話形式で収録を行い、編集後に公開します。事前に確認の機会を設けることも可能です。',
  },
]

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-white">
      {/* Page Header */}
      <div className="bg-slate-50 py-20 border-b border-slate-100">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <p className="text-teal-700 text-xs font-medium tracking-widest uppercase mb-3">About</p>
          <h1 className="text-3xl md:text-4xl font-bold text-slate-900">チャンネルについて</h1>
          <p className="mt-4 text-slate-600 max-w-xl leading-relaxed text-sm">
            The Curious Club（キュリクラ）は、医療と社会を題材にした対談・インタビューチャンネルです。好奇心を起点に、様々なゲストとリアルな会話を重ねています。
          </p>
        </div>
      </div>

      {/* Mission */}
      <section className="py-20">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
            <div>
              <p className="text-teal-700 text-xs font-medium tracking-widest uppercase mb-4">
                Mission
              </p>
              <h2 className="text-2xl md:text-3xl font-bold text-slate-900 leading-tight mb-6">
                「知る」ことが、
                <br />
                世界への入口になる。
              </h2>
              <div className="space-y-5 text-slate-600 leading-relaxed text-sm">
                <p>
                  医療の世界は、多くの人にとってまだ遠い存在です。病院に行かなければ接点がなく、専門的な情報は難解で、現場の人の声はほとんど届かない。
                </p>
                <p>
                  そこに「会話」という入口を作りたいと考えています。対談形式で、ゲストの生の言葉を引き出すことで、医療や社会の「リアル」を届けていきます。
                </p>
                <p>
                  視聴者の皆さんにとって、このチャンネルが「好奇心で世界をひらく」きっかけになれば幸いです。
                </p>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              {achievements.map((item) => (
                <div key={item.label} className="bg-slate-50 rounded-2xl p-6 text-center">
                  <p className="text-3xl font-bold text-teal-700">
                    {item.value}
                    <span className="text-lg">{item.unit}</span>
                  </p>
                  <p className="text-xs text-slate-500 mt-2 font-medium">{item.label}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Values */}
      <section className="py-20 bg-slate-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <p className="text-teal-700 text-xs font-medium tracking-widest uppercase mb-4">Values</p>
          <h2 className="text-2xl md:text-3xl font-bold text-slate-900 mb-12">こだわりと価値観</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {values.map((v) => (
              <div key={v.title} className="bg-white rounded-2xl p-8 border border-slate-100">
                <div className="w-8 h-1 bg-teal-600 rounded-full mb-4" />
                <h3 className="text-base font-semibold text-slate-900 mb-3">{v.title}</h3>
                <p className="text-sm text-slate-600 leading-relaxed">{v.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Host */}
      <section className="py-20">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <p className="text-teal-700 text-xs font-medium tracking-widest uppercase mb-4">Host</p>
          <h2 className="text-2xl md:text-3xl font-bold text-slate-900 mb-12">運営者について</h2>
          <div className="max-w-2xl">
            <div className="flex items-start gap-6">
              <Image
                src="/logo-icon.png"
                alt="The Curious Club キュリクラ"
                width={80}
                height={80}
                className="rounded-full flex-shrink-0"
              />
              <div>
                <h3 className="text-lg font-semibold text-slate-900">
                  The Curious Club 編集部
                </h3>
                <p className="text-sm text-slate-500 mt-1">チャンネル運営・企画・編集</p>
                <p className="mt-4 text-sm text-slate-600 leading-relaxed">
                  医療と社会の交差点に立ち、「知ること」と「伝えること」を追求しています。好奇心を道しるべに、様々なゲストとの会話を重ねていきます。
                </p>
                <p className="mt-3 text-xs text-slate-400">
                  ※ 詳細プロフィールは準備中です。
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Request Flow */}
      <section id="request-flow" className="py-20 bg-slate-900">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <p className="text-teal-400 text-xs font-medium tracking-widest uppercase mb-4">
            Request Flow
          </p>
          <h2 className="text-2xl md:text-3xl font-bold text-white mb-3">依頼の流れ</h2>
          <p className="text-slate-400 text-sm mb-14 max-w-xl leading-relaxed">
            出演・取材依頼からコラボレーション、メディア掲載まで、お気軽にご相談ください。
          </p>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            {requestSteps.map((step, i) => (
              <div key={step.step} className="relative">
                {i < requestSteps.length - 1 && (
                  <div className="hidden md:block absolute top-5 left-full w-full h-px bg-slate-700 -translate-x-4" />
                )}
                <div className="text-5xl font-bold text-teal-900 mb-4 leading-none">
                  {step.step}
                </div>
                <h3 className="text-white font-semibold mb-2">{step.title}</h3>
                <p className="text-slate-400 text-sm leading-relaxed">{step.description}</p>
              </div>
            ))}
          </div>

          <div className="mt-14 pt-12 border-t border-slate-800 text-center">
            <Link
              href="/contact"
              className="inline-flex items-center justify-center bg-teal-600 text-white px-8 py-4 rounded-full text-sm font-semibold hover:bg-teal-700 transition-colors"
            >
              お問い合わせフォームへ
            </Link>
          </div>
        </div>
      </section>
    </div>
  )
}
