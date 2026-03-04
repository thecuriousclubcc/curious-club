'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useState } from 'react'
import { Menu, X } from 'lucide-react'

const navLinks = [
  { href: '/', label: 'ホーム' },
  { href: '/videos', label: '動画一覧' },
  { href: '/about', label: 'About' },
  { href: '/contact', label: 'お問い合わせ' },
]

export default function Header() {
  const [isOpen, setIsOpen] = useState(false)
  const pathname = usePathname()

  return (
    <header className="sticky top-0 z-50 bg-white/90 backdrop-blur-sm border-b border-slate-100">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2.5 group">
            <span className="text-lg font-bold tracking-tight text-slate-900 group-hover:text-teal-700 transition-colors">
              The Curious Club
            </span>
            <span className="text-xs text-slate-400 font-light tracking-widest hidden sm:block">
              キュリクラ
            </span>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-7">
            {navLinks.slice(0, -1).map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`text-sm font-medium transition-colors ${
                  pathname === link.href
                    ? 'text-teal-700'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {link.label}
              </Link>
            ))}
            <Link
              href="/contact"
              className="text-sm bg-teal-700 text-white px-5 py-2 rounded-full hover:bg-teal-800 transition-colors font-medium"
            >
              相談する
            </Link>
          </nav>

          {/* Mobile menu button */}
          <button
            className="md:hidden p-2 text-slate-600 hover:text-slate-900 transition-colors"
            onClick={() => setIsOpen(!isOpen)}
            aria-label={isOpen ? 'メニューを閉じる' : 'メニューを開く'}
          >
            {isOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>

        {/* Mobile nav */}
        {isOpen && (
          <div className="md:hidden py-4 border-t border-slate-100">
            <nav className="flex flex-col gap-1">
              {navLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`text-sm py-2.5 px-2 rounded-lg transition-colors ${
                    pathname === link.href
                      ? 'text-teal-700 bg-teal-50 font-medium'
                      : 'text-slate-700 hover:bg-slate-50'
                  }`}
                  onClick={() => setIsOpen(false)}
                >
                  {link.label}
                </Link>
              ))}
              <Link
                href="/contact"
                className="mt-2 text-sm bg-teal-700 text-white px-4 py-3 rounded-xl hover:bg-teal-800 transition-colors text-center font-medium"
                onClick={() => setIsOpen(false)}
              >
                相談する
              </Link>
            </nav>
          </div>
        )}
      </div>
    </header>
  )
}
