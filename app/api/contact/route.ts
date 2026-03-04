import { NextRequest, NextResponse } from 'next/server'

interface ContactPayload {
  name: string
  email: string
  type: string
  message: string
}

export async function POST(req: NextRequest) {
  try {
    const body: ContactPayload = await req.json()
    const { name, email, type, message } = body

    if (!name || !email || !type || !message) {
      return NextResponse.json({ error: '必須項目が不足しています' }, { status: 400 })
    }

    // TODO: メール送信ロジックをここに追加
    // 例: Resend, SendGrid, Nodemailer など
    // 送信先: thecuriousclub.cc@gmail.com
    // await sendEmail({ to: 'thecuriousclub.cc@gmail.com', from: email, subject: `[お問い合わせ] ${type}`, body: ... })

    console.log('[Contact Form]', { name, email, type, message })

    return NextResponse.json({ message: '送信が完了しました' }, { status: 200 })
  } catch (error) {
    console.error('[Contact API Error]', error)
    return NextResponse.json({ error: 'サーバーエラーが発生しました' }, { status: 500 })
  }
}
