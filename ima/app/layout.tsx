import type { Metadata, Viewport } from 'next'
import './globals.css'
import { themeBootstrapScript } from '@/lib/bootstrap'

export const metadata: Metadata = {
  title: 'いま',
  description: 'One thing at a time.',
  manifest: '/manifest.webmanifest',
  appleWebApp: { capable: true, title: 'いま', statusBarStyle: 'default' },
  icons: {
    icon: [
      { url: '/icon-192.png', sizes: '192x192', type: 'image/png' },
      { url: '/icon-512.png', sizes: '512x512', type: 'image/png' },
    ],
    apple: '/icon-192.png',
  },
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  // The app is a fixed-layout tool, and a pinch-zoom here only ever happens by
  // accident mid-tap.
  maximumScale: 1,
  viewportFit: 'cover',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <head>
        {/* Runs before first paint so the launch never flashes the wrong skin. */}
        <script dangerouslySetInnerHTML={{ __html: themeBootstrapScript() }} />
      </head>
      <body className="min-h-screen">{children}</body>
    </html>
  )
}
