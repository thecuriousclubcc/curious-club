'use client'

import { useState, useRef } from 'react'
import { Turnstile } from '@marsidev/react-turnstile'
import type { TurnstileInstance } from '@marsidev/react-turnstile'

type FormStatus = 'idle' | 'submitting' | 'success' | 'error'

interface FormData {
  name: string
  email: string
  type: string
  message: string
}

const inputBase =
  'w-full px-4 py-3 rounded-xl border text-sm outline-none transition-colors focus:ring-2 focus:ring-teal-500 focus:border-teal-500'
const inputNormal = 'border-slate-200 bg-white'
const inputError = 'border-red-400 bg-red-50'

export default function ContactForm() {
  const [form, setForm] = useState<FormData>({ name: '', email: '', type: '', message: '' })
  const [status, setStatus] = useState<FormStatus>('idle')
  const [errors, setErrors] = useState<Partial<FormData>>({})
  const turnstileRef = useRef<TurnstileInstance>(null)

  const validate = (): boolean => {
    const newErrors: Partial<FormData> = {}
    if (!form.name.trim()) newErrors.name = 'お名前を入力してください'
    if (!form.email.trim()) newErrors.email = 'メールアドレスを入力してください'
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email))
      newErrors.email = '正しいメールアドレスを入力してください'
    if (!form.type) newErrors.type = 'お問い合わせ種別を選択してください'
    if (!form.message.trim()) newErrors.message = 'メッセージを入力してください'
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return

    const turnstileToken = turnstileRef.current?.getResponse()
    if (!turnstileToken) {
      setStatus('error')
      return
    }

    setStatus('submitting')
    try {
      const res = await fetch('/api/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, turnstileToken }),
      })
      if (res.ok) {
        setStatus('success')
        setForm({ name: '', email: '', type: '', message: '' })
      } else {
        setStatus('error')
        turnstileRef.current?.reset()
      }
    } catch {
      setStatus('error')
      turnstileRef.current?.reset()
    }
  }

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }))
    if (errors[e.target.name as keyof FormData]) {
      setErrors((prev) => ({ ...prev, [e.target.name]: undefined }))
    }
  }

  if (status === 'success') {
    return (
      <div className="text-center py-12">
        <div className="w-16 h-16 rounded-full bg-teal-50 flex items-center justify-center mx-auto mb-6">
          <svg
            className="w-8 h-8 text-teal-600"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h3 className="text-xl font-semibold text-slate-900 mb-2">送信完了しました</h3>
        <p className="text-slate-600 text-sm mb-8 leading-relaxed">
          お問い合わせいただきありがとうございます。
          <br />
          3営業日以内にご返信いたします。
        </p>
        <button
          onClick={() => setStatus('idle')}
          className="text-sm text-teal-700 underline underline-offset-4 hover:text-teal-900 transition-colors"
        >
          新しいお問い合わせをする
        </button>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6" noValidate>
      {/* Name */}
      <div>
        <label htmlFor="name" className="block text-sm font-medium text-slate-700 mb-2">
          お名前 <span className="text-red-500">*</span>
        </label>
        <input
          id="name"
          name="name"
          type="text"
          value={form.name}
          onChange={handleChange}
          placeholder="山田 太郎"
          className={`${inputBase} ${errors.name ? inputError : inputNormal}`}
        />
        {errors.name && <p className="mt-1.5 text-xs text-red-500">{errors.name}</p>}
      </div>

      {/* Email */}
      <div>
        <label htmlFor="email" className="block text-sm font-medium text-slate-700 mb-2">
          メールアドレス <span className="text-red-500">*</span>
        </label>
        <input
          id="email"
          name="email"
          type="email"
          value={form.email}
          onChange={handleChange}
          placeholder="example@email.com"
          className={`${inputBase} ${errors.email ? inputError : inputNormal}`}
        />
        {errors.email && <p className="mt-1.5 text-xs text-red-500">{errors.email}</p>}
      </div>

      {/* Type */}
      <div>
        <label htmlFor="type" className="block text-sm font-medium text-slate-700 mb-2">
          お問い合わせ種別 <span className="text-red-500">*</span>
        </label>
        <select
          id="type"
          name="type"
          value={form.type}
          onChange={handleChange}
          className={`${inputBase} bg-white ${errors.type ? inputError : inputNormal}`}
        >
          <option value="">選択してください</option>
          <option value="appearance">出演依頼</option>
          <option value="interview">取材・インタビュー依頼</option>
          <option value="collaboration">コラボレーション・タイアップ</option>
          <option value="media">メディア掲載・転載許可</option>
          <option value="other">その他</option>
        </select>
        {errors.type && <p className="mt-1.5 text-xs text-red-500">{errors.type}</p>}
      </div>

      {/* Message */}
      <div>
        <label htmlFor="message" className="block text-sm font-medium text-slate-700 mb-2">
          メッセージ <span className="text-red-500">*</span>
        </label>
        <textarea
          id="message"
          name="message"
          value={form.message}
          onChange={handleChange}
          rows={6}
          placeholder="ご依頼の内容・ご要望・ご質問など、詳しくお聞かせください。"
          className={`${inputBase} resize-none ${errors.message ? inputError : inputNormal}`}
        />
        {errors.message && <p className="mt-1.5 text-xs text-red-500">{errors.message}</p>}
      </div>

      {/* Turnstile */}
      <Turnstile
        ref={turnstileRef}
        siteKey={process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY!}
      />

      {status === 'error' && (
        <div className="p-4 bg-red-50 rounded-xl text-sm text-red-600 border border-red-100">
          送信に失敗しました。しばらく時間をおいてから再度お試しください。
        </div>
      )}

      <button
        type="submit"
        disabled={status === 'submitting'}
        className="w-full bg-teal-700 text-white py-4 rounded-xl text-sm font-semibold hover:bg-teal-800 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
      >
        {status === 'submitting' ? '送信中...' : '送信する'}
      </button>
    </form>
  )
}
