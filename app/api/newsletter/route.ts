import { NextRequest, NextResponse } from 'next/server'
import { Resend } from 'resend'
import { rateLimit, clientIp } from '@/lib/rate-limit'

function getResend() { return new Resend(process.env.RESEND_API_KEY) }

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export async function POST(req: NextRequest) {
  const { ok } = rateLimit(`newsletter:${clientIp(req)}`, 5, 60_000)
  if (!ok) {
    return NextResponse.json({ error: 'しばらく経ってからお試しください' }, { status: 429 })
  }

  const body = await req.json().catch(() => ({}))
  const { email, website } = body as { email?: unknown; website?: unknown }

  // Honeypot: real users never fill this hidden field — pretend success for bots
  if (website) {
    return NextResponse.json({ message: '登録しました' })
  }

  if (!email || typeof email !== 'string' || !EMAIL_RE.test(email) || email.length > 254) {
    return NextResponse.json({ error: '有効なメールアドレスを入力してください' }, { status: 400 })
  }

  const audienceId = process.env.RESEND_AUDIENCE_ID
  if (!audienceId) {
    // Silently succeed when audience is not configured (dev / missing env)
    return NextResponse.json({ message: '登録しました' })
  }

  try {
    await getResend().contacts.create({
      email,
      audienceId,
      unsubscribed: false,
    })
    return NextResponse.json({ message: '登録しました' })
  } catch (err: unknown) {
    // Resend returns 409 if contact already exists — treat as success
    const errObj = err as { statusCode?: number }
    if (errObj?.statusCode === 409) {
      return NextResponse.json({ message: '登録済みです' })
    }
    console.error('[Newsletter API Error]', err)
    return NextResponse.json({ error: 'サーバーエラーが発生しました' }, { status: 500 })
  }
}
