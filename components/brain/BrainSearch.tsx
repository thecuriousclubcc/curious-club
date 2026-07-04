'use client'

import { useState } from 'react'
import { Search, Play } from 'lucide-react'

interface Hit {
  video_title: string
  youtube_id: string
  published_on: string | null
  start_sec: number
  end_sec: number
  speaker: string | null
  quote: string
}

function mmss(sec: number): string {
  const s = Math.floor(sec)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const rest = `${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
  return h > 0 ? `${h}:${rest}` : rest
}

export default function BrainSearch() {
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState<Hit[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [playing, setPlaying] = useState<{ id: string; t: number } | null>(null)

  async function search() {
    const q = query.trim()
    if (q.length < 2) return
    setLoading(true)
    setPlaying(null)
    try {
      const r = await fetch(`/api/brain?q=${encodeURIComponent(q)}`)
      const d = await r.json()
      setHits(d.hits ?? [])
    } catch {
      setHits([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="flex gap-2 mb-8">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && search()}
          placeholder="例: 地域医療 / 開業 / 医学生へのメッセージ"
          className="flex-1 rounded-xl border border-slate-300 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600"
        />
        <button
          onClick={search}
          className="rounded-xl bg-teal-700 px-5 py-3 text-sm font-medium text-white hover:bg-teal-800 transition-colors"
        >
          <Search className="w-4 h-4" />
        </button>
      </div>

      {playing && (
        <div className="sticky top-4 z-10 mb-8 overflow-hidden rounded-2xl shadow-lg bg-black aspect-video">
          <iframe
            className="h-full w-full"
            src={`https://www.youtube.com/embed/${playing.id}?start=${Math.floor(playing.t)}&autoplay=1`}
            allow="autoplay; encrypted-media"
            allowFullScreen
            title="動画プレイヤー"
          />
        </div>
      )}

      {loading && <p className="text-sm text-slate-500">検索中…</p>}

      {hits !== null && !loading && hits.length === 0 && (
        <p className="text-sm text-slate-500">該当する発言は見つかりませんでした</p>
      )}

      <div className="space-y-4">
        {(hits ?? []).map((h, i) => (
          <div key={i} className="rounded-2xl border border-slate-200 bg-white p-5">
            <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span className="rounded-md bg-teal-50 px-2 py-0.5 font-medium text-teal-800">
                {mmss(h.start_sec)}–{mmss(h.end_sec)}
              </span>
              {h.speaker && <span className="font-medium text-slate-700">{h.speaker}</span>}
              <span className="truncate">{h.video_title}</span>
            </div>
            <p className="text-sm leading-relaxed text-slate-800">{h.quote}</p>
            <button
              onClick={() => setPlaying({ id: h.youtube_id, t: h.start_sec })}
              className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-slate-100 px-3 py-2 text-xs font-medium text-slate-800 hover:bg-teal-50 hover:text-teal-800 transition-colors"
            >
              <Play className="w-3.5 h-3.5" />
              {mmss(h.start_sec)} から再生
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
