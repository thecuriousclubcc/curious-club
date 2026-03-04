import Link from 'next/link'
import { Youtube, Instagram, Twitter } from 'lucide-react'

// SNSリンクのURLはここで差し替えてください
const socialLinks = [
  {
    name: 'YouTube',
    href: 'https://www.youtube.com/@TheCuriousClub_CC',
    icon: Youtube,
    label: 'YouTubeチャンネル',
  },
  {
    name: 'Instagram',
    href: 'https://www.instagram.com/thecuriousclub_cc/',
    icon: Instagram,
    label: 'Instagram',
  },
  {
    name: 'X (Twitter)',
    href: 'https://x.com/becurious4ever',
    icon: Twitter,
    label: 'X（旧Twitter）',
  },
]

const footerLinks = [
  { href: '/', label: 'ホーム' },
  { href: '/videos', label: '動画一覧' },
  { href: '/about', label: 'About' },
  { href: '/contact', label: 'お問い合わせ' },
]

export default function Footer() {
  return (
    <footer className="bg-slate-900 text-slate-400">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-10">
          {/* Brand */}
          <div>
            <p className="text-white text-base font-bold tracking-tight">The Curious Club</p>
            <p className="text-slate-500 text-xs tracking-widest mt-1">キュリクラ</p>
            <p className="mt-5 text-sm leading-relaxed">
              好奇心で世界をひらく。
              <br />
              医療と社会のリアルを、会話で届ける。
            </p>
          </div>

          {/* Sitemap */}
          <div>
            <p className="text-white text-xs font-semibold mb-5 tracking-wide uppercase">
              サイトマップ
            </p>
            <nav className="flex flex-col gap-3">
              {footerLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="text-sm text-slate-400 hover:text-teal-400 transition-colors"
                >
                  {link.label}
                </Link>
              ))}
            </nav>
          </div>

          {/* Social */}
          <div>
            <p className="text-white text-xs font-semibold mb-5 tracking-wide uppercase">
              SNS・外部リンク
            </p>
            <div className="flex flex-col gap-3">
              {socialLinks.map((social) => (
                <a
                  key={social.name}
                  href={social.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2.5 text-sm text-slate-400 hover:text-teal-400 transition-colors"
                >
                  <social.icon size={15} />
                  {social.label}
                </a>
              ))}
            </div>
          </div>
        </div>

        <div className="border-t border-slate-800 mt-12 pt-8 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-600">
          <p>© {new Date().getFullYear()} The Curious Club. All rights reserved.</p>
          <Link href="/contact" className="hover:text-slate-400 transition-colors">
            お問い合わせ
          </Link>
        </div>
      </div>
    </footer>
  )
}
