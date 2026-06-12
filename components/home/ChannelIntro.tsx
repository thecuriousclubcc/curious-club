const features = [
  {
    title: '問い・決断・生き方に迫る',
    description:
      '肩書きよりも、その人の葛藤や選択の瞬間に焦点を当てます。どんな問いを持ち、どう決断し、どう生きてきたのか。',
  },
  {
    title: '分野を超えたゲスト',
    description:
      '医療・教育・ビジネス・社会・カルチャー。さまざまな領域で"熱を持って生きる人"に会いに行きます。',
  },
  {
    title: '対話から生まれる本音',
    description:
      '台本なしの対話だから引き出せる、本音や葛藤、迷いの言葉。それが、番組の核心です。',
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
            The Curious Club（キュリクラ）は、現役医学生による対話型インタビュー企画です。医療、教育、ビジネス、社会、カルチャーなど、分野を超えて&quot;熱を持って生きる人&quot;に会いに行き、その人の問い、決断、リアルな生き方・キャリアを掘り下げます。
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
