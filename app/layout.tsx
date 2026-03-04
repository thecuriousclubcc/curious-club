import type { Metadata } from 'next'
import { Noto_Sans_JP } from 'next/font/google'
import Script from 'next/script'
import './globals.css'
import Header from '@/components/layout/Header'
import Footer from '@/components/layout/Footer'

const notoSansJP = Noto_Sans_JP({
  subsets: ['latin'],
  weight: ['300', '400', '500', '700'],
  variable: '--font-noto-sans-jp',
  display: 'swap',
})

export const metadata: Metadata = {
  title: {
    default: 'The Curious Club（キュリクラ）| 医療と社会を対話でひらく',
    template: '%s | The Curious Club（キュリクラ）',
  },
  description:
    '好奇心で世界をひらく。医療と社会のリアルを、会話で届けるYouTubeチャンネル「The Curious Club（キュリクラ）」公式サイト。出演・取材・お仕事のご依頼もお気軽にどうぞ。',
  keywords: ['医療', 'YouTube', '対談', 'インタビュー', 'The Curious Club', 'キュリクラ'],
  openGraph: {
    title: 'The Curious Club（キュリクラ）| 医療と社会を対話でひらく',
    description: '好奇心で世界をひらく。医療と社会のリアルを、会話で届ける。',
    url: 'https://curious-club.jp',
    siteName: 'The Curious Club（キュリクラ）',
    locale: 'ja_JP',
    type: 'website',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'The Curious Club（キュリクラ）',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'The Curious Club（キュリクラ）',
    description: '好奇心で世界をひらく。医療と社会のリアルを、会話で届ける。',
    images: ['/og-image.png'],
  },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja" className={notoSansJP.variable}>
      <body className="font-sans antialiased">
        <Script
          src="https://www.googletagmanager.com/gtag/js?id=G-WXL5VWXWYN"
          strategy="beforeInteractive"
        />
        <Script id="google-analytics" strategy="beforeInteractive">
          {`
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', 'G-WXL5VWXWYN');
          `}
        </Script>
        <Header />
        <main className="min-h-screen">{children}</main>
        <Footer />
      </body>
    </html>
  )
}
