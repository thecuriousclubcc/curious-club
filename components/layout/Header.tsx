'use client'

import Link from 'next/link'
import Image from 'next/image'
import { usePathname } from 'next/navigation'
import { useState, useEffect } from 'react'
import { Menu, X } from 'lucide-react'

const navLinks = [
  { href: '/', label: 'ホーム' },
  { href: '/videos', label: '動画一覧' },
  { href: '/about', label: 'About' },
  { href: '/contact', label: 'お問い合わせ' },
]

export default function Header() {
  const [isOpen, setIsOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const pathname = usePathname()

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 80)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const isHome = pathname === '/'
  const transparent = isHome && !scrolled

  return (
    <header className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${transparent ? 'bg-transparent' : 'bg-white/95 backdrop-blur-sm border-b border-slate-100'}`}>
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 group">
            <Image
              src="/logo-icon.png"
              alt="The Curious Club キュリクラ"
              width={60}
              height={60}
              className="rounded-full"
            />
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-7">
            {navLinks.slice(0, -1).map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`text-sm font-medium transition-colors ${
                  pathname === link.href
                    ? transparent ? 'text-white' : 'text-teal-700'
                    : transparent ? 'text-white/80 hover:text-white' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {link.label}
              </Link>
            ))}
            <Link
              href="/contact"
              className={`text-sm px-5 py-2 rounded-full transition-colors font-medium ${transparent ? 'bg-white/20 text-white hover:bg-white/30 backdrop-blur-sm' : 'bg-teal-700 text-white hover:bg-teal-800'}`}
            >
              お問い合わせ
            </Link>
          </nav>

          {/* Mobile menu button */}
          <button
            className={`md:hidden p-2 transition-colors ${transparent ? 'text-white hover:text-white/80' : 'text-slate-600 hover:text-slate-900'}`}
            onClick={() => setIsOpen(!isOpen)}
            aria-label={isOpen ? 'メニューを閉じる' : 'メニューを開く'}
          >
            {isOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>

        {/* Mobile nav */}
        {isOpen && (
          <div className={`md:hidden py-4 border-t ${transparent ? 'border-white/20 bg-black/60 backdrop-blur-sm' : 'border-slate-100 bg-white'}`}>
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
                お問い合わせ
              </Link>
            </nav>
          </div>
        )}
      </div>
    </header>
  )
}
