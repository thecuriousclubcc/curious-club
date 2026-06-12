import type { Enrichment } from '@/lib/enrichment'
import { Sparkles, Quote } from 'lucide-react'

interface Props {
  enrichment: Enrichment
}

export default function EpisodeSummary({ enrichment }: Props) {
  return (
    <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-6 space-y-5">
      {/* Header */}
      <div className="flex items-center gap-2 text-teal-700">
        <Sparkles size={16} />
        <span className="text-xs font-semibold tracking-widest uppercase">AI Summary</span>
      </div>

      {/* Summary */}
      <p className="text-sm text-slate-700 leading-relaxed">{enrichment.summary}</p>

      {/* Key themes */}
      {enrichment.keyThemes.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {enrichment.keyThemes.map((theme) => (
            <span
              key={theme}
              className="text-xs text-teal-700 bg-teal-50 px-3 py-1.5 rounded-full border border-teal-100"
            >
              {theme}
            </span>
          ))}
        </div>
      )}

      {/* Key quotes */}
      {enrichment.keyQuotes.length > 0 && (
        <div className="space-y-3 pt-2">
          {enrichment.keyQuotes.map((quote, i) => (
            <blockquote
              key={i}
              className="relative pl-4 border-l-2 border-teal-300 text-sm text-slate-600 italic leading-relaxed"
            >
              <Quote size={12} className="absolute -left-1 -top-1 text-teal-300" />
              {quote}
            </blockquote>
          ))}
        </div>
      )}

      {/* Suggested questions */}
      {enrichment.suggestedQuestions.length > 0 && (
        <div className="pt-2">
          <p className="text-xs font-medium text-slate-500 mb-3">この動画を見たら考えたいこと</p>
          <ul className="space-y-2">
            {enrichment.suggestedQuestions.map((q, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-600">
                <span className="text-teal-500 mt-0.5 shrink-0">Q.</span>
                {q}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
