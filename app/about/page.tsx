import type { Metadata } from 'next'
import Image from 'next/image'
import Link from 'next/link'

export const metadata: Metadata = {
  title: 'About',
  description:
    'The Curious Club（キュリクラ）について。現役医学生による対話型インタビュー企画の活動内容、価値観、出演・取材依頼の流れをご紹介します。',
}

const achievements = [
  { label: '総動画数', value: '60+', unit: '本' },
  { label: '出演ゲスト', value: '13', unit: '名' },
  { label: '開始', value: '2025', unit: '年' },
]

const values = [
  {
    title: '問い・決断・生き方に迫る',
    body: '肩書きや実績よりも、その人の葛藤、違和感、選択の瞬間を大切にしています。どんな問いを持ち、どう決断してきたかに迫ります。',
  },
  {
    title: '台本なしの対話',
    body: '事前に話す内容を決めすぎません。その場で生まれる問いと答えが、番組の核心だと考えているからです。',
  },
  {
    title: '分野を超えたゲスト',
    body: '医療はもちろん、教育、ビジネス、社会、カルチャーなど、さまざまな領域で"熱を持って生きる人"をお招きします。',
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
          <h1 className="text-3xl md:text-4xl font-bold text-slate-900">キュリクラについて</h1>
          <p className="mt-4 text-slate-600 max-w-xl leading-relaxed text-sm">
            現役医学生による対話型インタビュー企画。医療、教育、ビジネス、社会、カルチャーなど、分野を超えて&quot;熱を持って生きる人&quot;に出会い、その人の問い、決断、リアルな生き方・キャリアに迫ります。
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
                「この人は、どんな問いを持って
                <br />
                どう決断して、生きてきたのか。」
              </h2>
              <div className="space-y-5 text-slate-600 leading-relaxed text-sm">
                <p>
                  キャリアのこと、葛藤のこと、選択の分岐点——。そういう話を、正直に語ってくれる大人に出会える機会は、思ったより少ない。
                </p>
                <p>
                  キュリクラは、肩書きよりも&quot;その人の内側&quot;に迫るインタビュー企画です。医療、教育、ビジネス、社会、カルチャーなど分野を超えて、熱を持って生きるゲストと対話を重ねています。
                </p>
                <p>
                  「この人の話、聞いてよかった」「自分もこう考えてみよう」——見た人にとって、そんなきっかけになれれば。それが、一番の目標です。
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
                  現役医学生として、医療の内側と外側の両方に好奇心を持ち、「自分が話を聞きたい人」に会いに行くことをモチベーションに活動しています。
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
