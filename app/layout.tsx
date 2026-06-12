import type { Metadata } from 'next'
import Script from 'next/script'
import { Noto_Sans_JP } from 'next/font/google'
import './globals.css'
import Header from '@/components/layout/Header'
import Footer from '@/components/layout/Footer'
import AskWidget from '@/components/AskWidget'
import { SITE_URL } from '@/lib/site'

const notoSansJP = Noto_Sans_JP({
  subsets: ['latin'],
  weight: ['300', '400', '500', '700'],
  variable: '--font-noto-sans-jp',
  display: 'swap',
})

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  alternates: {
    canonical: './',
  },
  title: {
    default: 'The Curious Club（キュリクラ）| あなたの問い、決断、リアルな生き方に迫る。',
    template: '%s | The Curious Club（キュリクラ）',
  },
  description:
    '現役医学生による対話型インタビュー企画。医療、教育、ビジネス、社会、カルチャーなど、分野を超えて"熱を持って生きる人"に出会い、その人の問い、決断、リアルな生き方・キャリアに迫ります。',
  keywords: ['医学生', 'インタビュー', '対話', 'キャリア', 'The Curious Club', 'キュリクラ'],
  openGraph: {
    title: 'The Curious Club（キュリクラ）| あなたの問い、決断、リアルな生き方に迫る。',
    description: '分野を超えて"熱を持って生きる人"に会いに行く。現役医学生による対話型インタビュー企画。',
    url: SITE_URL,
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
    description: '分野を超えて"熱を持って生きる人"に会いに行く。現役医学生による対話型インタビュー企画。',
    images: ['/og-image.png'],
  },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja" className={notoSansJP.variable}>
      <body className="font-sans antialiased">
        <Script
          src="https://www.googletagmanager.com/gtag/js?id=G-WXL5VWXWYN"
          strategy="afterInteractive"
        />
        <Script id="google-analytics" strategy="afterInteractive">
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
        <AskWidget />
      </body>
    </html>
  )
}
