'use client'

import Link from 'next/link'
import { useState } from 'react'
import { Send } from 'lucide-react'

function NewsletterForm() {
  const [email, setEmail] = useState('')
  const [website, setWebsite] = useState('') // honeypot — bots fill it, humans never see it
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!email.trim() || status === 'loading') return

    setStatus('loading')
    try {
      const res = await fetch('/api/newsletter', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, website }),
      })
      const data = await res.json()
      if (res.ok) {
        setStatus('success')
        setMessage(data.message ?? '登録しました')
        setEmail('')
      } else {
        setStatus('error')
        setMessage(data.error ?? 'エラーが発生しました')
      }
    } catch {
      setStatus('error')
      setMessage('通信エラーが発生しました')
    }
  }

  if (status === 'success') {
    return (
      <p className="text-teal-200 text-sm mt-6">{message} メールをお待ちください。</p>
    )
  }

  return (
    <form onSubmit={submit} className="mt-6 flex flex-col sm:flex-row gap-2 max-w-md mx-auto">
      <input
        type="text"
        name="website"
        value={website}
        onChange={(e) => setWebsite(e.target.value)}
        tabIndex={-1}
        autoComplete="off"
        aria-hidden="true"
        className="absolute -left-[9999px] h-0 w-0 opacity-0"
      />
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="メールアドレスを入力"
        required
        className="flex-1 px-4 py-3 rounded-full text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-white bg-white/90"
      />
      <button
        type="submit"
        disabled={status === 'loading'}
        className="flex items-center justify-center gap-2 px-6 py-3 bg-white text-teal-900 rounded-full text-sm font-semibold hover:bg-teal-50 transition-colors disabled:opacity-60"
      >
        <Send size={14} />
        登録
      </button>
      {status === 'error' && (
        <p className="w-full text-red-300 text-xs mt-1">{message}</p>
      )}
    </form>
  )
}

export default function CTASection() {
  return (
    <section className="py-28 bg-teal-900">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <h2 className="text-3xl md:text-4xl font-bold text-white leading-tight">
          あなたの話を、聞かせてください。
        </h2>
        <p className="mt-6 text-teal-200 text-base md:text-lg leading-relaxed max-w-xl mx-auto">
          出演・取材・コラボなど、まずはお気軽にご連絡ください。
        </p>
        <div className="mt-10 flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            href="/contact"
            className="inline-flex items-center justify-center bg-white text-teal-900 px-8 py-4 rounded-full text-sm font-semibold hover:bg-teal-50 transition-colors"
          >
            お問い合わせ
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

        {/* Newsletter */}
        <div className="mt-16 pt-10 border-t border-teal-800">
          <p className="text-white font-semibold text-lg">新着エピソードを見逃さない</p>
          <p className="mt-2 text-teal-300 text-sm">新しいインタビューが公開されたらメールでお知らせします。</p>
          <NewsletterForm />
        </div>
      </div>
    </section>
  )
}
