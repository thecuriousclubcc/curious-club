const features = [
  {
    title: '台本なしの対話',
    description:
      'あらかじめ決められた展開はなし。その場で生まれる問いと答えが、番組の核心です。',
  },
  {
    title: '医療×社会の交差点',
    description:
      '医師・看護師・研究者・患者——さまざまな立場から、医療と社会の現実に迫ります。',
  },
  {
    title: '熱量と誠実さ',
    description:
      '「これは言っていいのか」という際どい話を含め、本音で語り合うことを大切にしています。',
  },
]

export default function ChannelIntro() {
  return (
    <section className="py-24 bg-white">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="max-w-2xl mb-16">
          <p className="text-teal-700 text-xs font-medium tracking-widest uppercase mb-3">
            About the Channel
          </p>
          <h2 className="text-3xl md:text-4xl font-bold text-slate-900 leading-tight">
            「キュリクラ」が、
            <br />
            大切にしていること
          </h2>
          <p className="mt-5 text-slate-600 leading-relaxed text-sm">
            The Curious Club（キュリクラ）は、医療と社会をテーマにした対談・インタビュー形式のYouTubeチャンネルです。知識を「伝える」だけでなく、現場のリアルな声を「会話の形で届ける」ことを大切にしています。
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {features.map((feature, i) => (
            <div key={i} className="p-8 bg-slate-50 rounded-2xl">
              <div className="w-8 h-1 bg-teal-600 rounded-full mb-5" />
              <h3 className="text-base font-semibold text-slate-900 mb-3">{feature.title}</h3>
              <p className="text-sm text-slate-600 leading-relaxed">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
