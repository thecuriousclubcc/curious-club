import { NextRequest, NextResponse } from 'next/server'
import { Resend } from 'resend'

const resend = new Resend(process.env.RESEND_API_KEY)

const typeLabels: Record<string, string> = {
  appearance: '出演依頼',
  interview: '取材・インタビュー依頼',
  collaboration: 'コラボレーション・タイアップ',
  media: 'メディア掲載・転載許可',
  other: 'その他',
}

interface ContactPayload {
  name: string
  email: string
  type: string
  message: string
  turnstileToken: string
}

export async function POST(req: NextRequest) {
  try {
    const body: ContactPayload = await req.json()
    const { name, email, type, message, turnstileToken } = body

    if (!name || !email || !type || !message || !turnstileToken) {
      return NextResponse.json({ error: '必須項目が不足しています' }, { status: 400 })
    }

    if (name.length > 100 || email.length > 254 || message.length > 3000) {
      return NextResponse.json({ error: '入力内容が長すぎます' }, { status: 400 })
    }

    if (!typeLabels[type]) {
      return NextResponse.json({ error: '無効なお問い合わせ種別です' }, { status: 400 })
    }

    // Verify Turnstile token
    const verifyRes = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        secret: process.env.TURNSTILE_SECRET_KEY,
        response: turnstileToken,
      }),
    })
    const verifyData = await verifyRes.json()
    if (!verifyData.success) {
      return NextResponse.json({ error: '認証に失敗しました' }, { status: 400 })
    }

    const typeLabel = typeLabels[type]

    await resend.emails.send({
      from: 'The Curious Club <onboarding@resend.dev>',
      to: 'thecuriousclub.cc@gmail.com',
      replyTo: email,
      subject: `[お問い合わせ] ${typeLabel} — ${name}`,
      text: `■ お問い合わせ種別\n${typeLabel}\n\n■ お名前\n${name}\n\n■ メールアドレス\n${email}\n\n■ メッセージ\n${message}`,
    })

    return NextResponse.json({ message: '送信が完了しました' }, { status: 200 })
  } catch (error) {
    console.error('[Contact API Error]', error)
    return NextResponse.json({ error: 'サーバーエラーが発生しました' }, { status: 500 })
  }
}
