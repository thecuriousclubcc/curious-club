import { NextRequest, NextResponse } from 'next/server'
import { Resend } from 'resend'

function getResend() { return new Resend(process.env.RESEND_API_KEY) }

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export async function POST(req: NextRequest) {
  const { email } = await req.json()

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
