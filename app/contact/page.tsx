import type { Metadata } from 'next'
import Link from 'next/link'
import ContactForm from '@/components/contact/ContactForm'

export const metadata: Metadata = {
  title: 'お問い合わせ',
  description:
    '出演依頼・取材依頼・コラボレーション・その他のお問い合わせはこちらから。3営業日以内にご返信いたします。',
}

const contactTypes = [
  '出演依頼（医師・医療従事者・研究者の方など）',
  '取材・インタビュー依頼',
  'コラボレーション・タイアップ',
  'メディア掲載・転載許可',
  'その他ご相談',
]

export default function ContactPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-start">
          {/* Left: Info */}
          <div>
            <p className="text-teal-700 text-xs font-medium tracking-widest uppercase mb-3">
              Contact
            </p>
            <h1 className="text-3xl md:text-4xl font-bold text-slate-900 mb-6">お問い合わせ</h1>
            <p className="text-slate-600 leading-relaxed mb-8 text-sm">
              出演・取材依頼、コラボレーション、メディア掲載など、お気軽にご相談ください。
              <br />
              3営業日以内にご返信いたします。
            </p>

            <div className="space-y-5">
              <div className="p-6 bg-white rounded-2xl border border-slate-100">
                <h3 className="text-sm font-semibold text-slate-900 mb-3">
                  受け付けているご依頼
                </h3>
                <ul className="text-sm text-slate-600 space-y-2">
                  {contactTypes.map((item) => (
                    <li key={item} className="flex items-start gap-2">
                      <span className="text-teal-600 mt-0.5 flex-shrink-0">•</span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="p-6 bg-white rounded-2xl border border-slate-100">
                <h3 className="text-sm font-semibold text-slate-900 mb-2">
                  依頼の流れを確認する
                </h3>
                <p className="text-sm text-slate-600 mb-4">
                  お問い合わせから公開までのステップをご確認いただけます。
                </p>
                <Link
                  href="/about#request-flow"
                  className="text-sm text-teal-700 font-medium underline underline-offset-4 hover:text-teal-900 transition-colors"
                >
                  依頼の流れを見る →
                </Link>
              </div>
            </div>
          </div>

          {/* Right: Form */}
          <div className="bg-white rounded-2xl p-8 shadow-sm border border-slate-100">
            <ContactForm />
          </div>
        </div>
      </div>
    </div>
  )
}
