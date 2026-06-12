'use client'

import { useState } from 'react'
import { Lightbulb, ChevronDown } from 'lucide-react'

interface Props {
  insights: string[]
}

export default function CareerInsights({ insights }: Props) {
  const [open, setOpen] = useState(false)

  if (insights.length === 0) return null

  return (
    <div className="bg-amber-50 rounded-2xl border border-amber-100 shadow-sm overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between p-6 text-left hover:bg-amber-100/40 transition-colors"
      >
        <div className="flex items-center gap-2 text-amber-700">
          <Lightbulb size={16} />
          <span className="text-xs font-semibold tracking-widest uppercase">
            キャリアへの示唆
          </span>
        </div>
        <ChevronDown
          size={16}
          className={`text-amber-500 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <ul className="px-6 pb-6 space-y-3">
          {insights.map((insight, i) => (
            <li key={i} className="flex items-start gap-3 text-sm text-amber-900">
              <span className="text-amber-400 font-bold mt-0.5 shrink-0">{i + 1}.</span>
              {insight}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
