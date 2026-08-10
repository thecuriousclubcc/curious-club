'use client'

import { t, type Locale } from '@/lib/i18n'

export const TABS = ['now', 'in', 'day', 'all', 'me'] as const
export type Tab = (typeof TABS)[number]

/**
 * Five tabs, fixed order, and the order never changes for any theme. The skin
 * rotating every three days only works because position does not — a button
 * that stays put becomes automatic, and automatic costs no activation energy.
 */
export function TabBar({
  active,
  onChange,
  locale,
}: {
  active: Tab
  onChange: (tab: Tab) => void
  locale: Locale
}) {
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-10 flex border-t-token border-hairline bg-surface"
      style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
    >
      {TABS.map((tab) => {
        const selected = tab === active
        return (
          <button
            key={tab}
            type="button"
            onClick={() => onChange(tab)}
            aria-current={selected ? 'page' : undefined}
            className="flex min-h-tap flex-1 flex-col items-center justify-center gap-1 py-2 font-display text-[0.7rem] tracking-wider transition-colors duration-token"
            style={{ color: selected ? 'var(--accent)' : 'var(--muted)' }}
          >
            <span
              className="h-1 w-1 rounded-full"
              style={{ background: selected ? 'var(--accent)' : 'transparent' }}
            />
            {t(locale, `tab.${tab}`)}
          </button>
        )
      })}
    </nav>
  )
}
