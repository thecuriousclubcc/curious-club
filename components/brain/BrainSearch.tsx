'use client'

import { useMemo, useRef, useState } from 'react'
import { Search, Play, Clock, X, Sparkles } from 'lucide-react'

interface Hit {
  video_title: string
  youtube_id: string
  published_on: string | null
  start_sec: number
  end_sec: number
  speaker: string | null
  quote: string
}

interface VideoGroup {
  youtube_id: string
  video_title: string
  published_on: string | null
  hits: Hit[]
}

const SUGGESTIONS = ['地域医療', '開業', '医学生へのメッセージ', '屋台', '美容外科']

function mmss(sec: number): string {
  const s = Math.floor(sec)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const rest = `${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
  return h > 0 ? `${h}:${rest}` : rest
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function Highlight({ text, terms }: { text: string; terms: string[] }) {
  const pattern = useMemo(() => {
    const valid = terms.map((t) => t.trim()).filter((t) => t.length >= 2)
    return valid.length ? new RegExp(`(${valid.map(escapeRegExp).join('|')})`, 'g') : null
  }, [terms])
  if (!pattern) return <>{text}</>
  // String.split with a capturing group places matches at odd indices
  return (
    <>
      {text.split(pattern).map((part, i) =>
        i % 2 === 1 ? (
          <mark key={i} className="bg-teal-100 text-teal-900 rounded px-0.5">
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  )
}

function SkeletonCard() {
  return (
    <div className="rounded-2xl bg-white shadow-sm overflow-hidden">
      <div className="flex gap-4 p-5 animate-pulse">
        <div className="hidden sm:block w-40 shrink-0 aspect-video rounded-xl bg-slate-200" />
        <div className="flex-1 space-y-3 py-1">
          <div className="h-3 w-2/3 rounded bg-slate-200" />
          <div className="h-3 w-full rounded bg-slate-100" />
          <div className="h-3 w-5/6 rounded bg-slate-100" />
        </div>
      </div>
    </div>
  )
}

export default function BrainSearch() {
  const [query, setQuery] = useState('')
  const [searched, setSearched] = useState('')
  const [groups, setGroups] = useState<VideoGroup[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [playing, setPlaying] = useState<Hit | null>(null)
  const [answer, setAnswer] = useState<{ text: string; sources: Hit[] } | null>(null)
  const [asking, setAsking] = useState(false)
  const playerRef = useRef<HTMLDivElement>(null)

  async function askAI(q: string) {
    const trimmed = q.trim()
    if (trimmed.length < 2 || asking) return
    setQuery(trimmed)
    setSearched(trimmed)
    setGroups(null)
    setPlaying(null)
    setAnswer(null)
    setAsking(true)
    try {
      const r = await fetch('/api/brain/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: trimmed }),
      })
      const d = await r.json()
      setAnswer({ text: d.answer ?? '回答を生成できませんでした', sources: d.sources ?? [] })
    } catch {
      setAnswer({ text: '回答を生成できませんでした。もう一度お試しください。', sources: [] })
    } finally {
      setAsking(false)
    }
  }

  async function search(q: string) {
    const trimmed = q.trim()
    if (trimmed.length < 2) return
    setQuery(trimmed)
    setSearched(trimmed)
    setLoading(true)
    setPlaying(null)
    setAnswer(null)
    try {
      const r = await fetch(`/api/brain?q=${encodeURIComponent(trimmed)}`)
      const d = await r.json()
      const hits: Hit[] = d.hits ?? []
      const map = new Map<string, VideoGroup>()
      for (const h of hits) {
        const g = map.get(h.youtube_id) ?? {
          youtube_id: h.youtube_id,
          video_title: h.video_title,
          published_on: h.published_on,
          hits: [],
        }
        g.hits.push(h)
        map.set(h.youtube_id, g)
      }
      for (const g of map.values()) g.hits.sort((a, b) => a.start_sec - b.start_sec)
      setGroups([...map.values()])
    } catch {
      setGroups([])
    } finally {
      setLoading(false)
    }
  }

  function playHit(h: Hit) {
    setPlaying(h)
    requestAnimationFrame(() =>
      playerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
    )
  }

  const terms = searched.split(/\s+/)

  return (
    <div>
      {/* Search bar */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && search(query)}
            placeholder="気になるテーマ・言葉を入力"
            aria-label="動画内の発言を検索"
            className="w-full rounded-2xl border border-slate-200 bg-white py-3.5 pl-11 pr-4 text-base text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20"
          />
        </div>
        <button
          onClick={() => search(query)}
          aria-label="検索"
          className="min-w-[52px] cursor-pointer rounded-2xl bg-teal-700 px-5 text-sm font-medium text-white shadow-sm transition-colors duration-200 hover:bg-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-600/40"
        >
          検索
        </button>
        <button
          onClick={() => askAI(query)}
          disabled={asking}
          aria-label="AIに聞く"
          className="inline-flex cursor-pointer items-center gap-1.5 rounded-2xl border border-teal-700/30 bg-white px-4 text-sm font-medium text-teal-800 shadow-sm transition-colors duration-200 hover:bg-teal-50 focus:outline-none focus:ring-2 focus:ring-teal-600/40 disabled:opacity-50"
        >
          <Sparkles className="h-4 w-4" />
          <span className="hidden sm:inline">AIに聞く</span>
        </button>
      </div>

      {/* Suggestion chips */}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="text-xs text-slate-400">例:</span>
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => search(s)}
            className="cursor-pointer rounded-full bg-white border border-slate-200 px-3 py-1.5 text-xs text-slate-600 transition-colors duration-200 hover:border-teal-600 hover:text-teal-700"
          >
            {s}
          </button>
        ))}
      </div>

      {/* Player */}
      <div ref={playerRef} className="scroll-mt-24">
        {playing && (
          <div className="mt-8 overflow-hidden rounded-2xl bg-white shadow-md">
            <div className="aspect-video bg-black">
              <iframe
                className="h-full w-full"
                src={`https://www.youtube.com/embed/${playing.youtube_id}?start=${Math.floor(playing.start_sec)}&autoplay=1`}
                allow="autoplay; encrypted-media"
                allowFullScreen
                title={playing.video_title}
              />
            </div>
            <div className="flex items-start justify-between gap-3 p-5">
              <div>
                <p className="mb-1 flex items-center gap-2 text-xs text-slate-500">
                  <Clock className="h-3.5 w-3.5" />
                  {mmss(playing.start_sec)}–{mmss(playing.end_sec)}
                  {playing.speaker && (
                    <span className="font-medium text-teal-700">{playing.speaker}</span>
                  )}
                </p>
                <p className="text-sm leading-relaxed text-slate-800 line-clamp-2">
                  {playing.quote}
                </p>
              </div>
              <button
                onClick={() => setPlaying(null)}
                aria-label="プレイヤーを閉じる"
                className="cursor-pointer rounded-full p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* AI answer */}
      {asking && (
        <div className="mt-8 rounded-2xl border border-teal-100 bg-teal-50/50 p-6">
          <p className="flex items-center gap-2 text-sm text-teal-800">
            <Sparkles className="h-4 w-4 animate-pulse" />
            全エピソードの発言を確認しています…
          </p>
        </div>
      )}
      {answer && !asking && (
        <div className="mt-8 overflow-hidden rounded-2xl border border-teal-100 bg-white shadow-sm">
          <div className="border-b border-teal-50 bg-teal-50/50 px-5 py-3">
            <p className="flex items-center gap-2 text-xs font-medium tracking-wide text-teal-800">
              <Sparkles className="h-3.5 w-3.5" />
              AI回答 — 引用は実際の発言と機械照合済み
            </p>
          </div>
          <p className="whitespace-pre-wrap p-5 text-sm leading-relaxed text-slate-800">
            {answer.text}
          </p>
          {answer.sources.length > 0 && (
            <ul className="divide-y divide-slate-50 border-t border-slate-100">
              {answer.sources.map((s, i) => (
                <li key={i}>
                  <button
                    onClick={() => playHit(s)}
                    className="group flex w-full cursor-pointer items-start gap-4 p-5 text-left transition-colors duration-200 hover:bg-slate-50"
                  >
                    <span className="mt-0.5 inline-flex shrink-0 items-center gap-1 rounded-lg bg-teal-50 px-2.5 py-1.5 text-xs font-semibold tabular-nums text-teal-800 group-hover:bg-teal-100">
                      <Play className="h-3 w-3" fill="currentColor" />
                      {mmss(s.start_sec)}
                    </span>
                    <span className="min-w-0">
                      <span className="mb-1 block text-xs text-slate-500">
                        {s.speaker && <span className="font-medium">{s.speaker} · </span>}
                        {s.video_title}
                      </span>
                      <span className="block text-sm leading-relaxed text-slate-800 line-clamp-2">
                        「{s.quote}」
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Results */}
      <div className="mt-8 space-y-6">
        {loading && (
          <>
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </>
        )}

        {!loading && groups !== null && groups.length === 0 && (
          <div className="rounded-2xl bg-white p-10 text-center shadow-sm">
            <p className="text-sm font-medium text-slate-700">
              「{searched}」に該当する発言は見つかりませんでした
            </p>
            <p className="mt-2 text-xs leading-relaxed text-slate-500">
              別の言い回しや、話題のキーワード（治療名・地名・人名など）で試してみてください
            </p>
          </div>
        )}

        {!loading &&
          (groups ?? []).map((g) => (
            <section key={g.youtube_id} className="overflow-hidden rounded-2xl bg-white shadow-sm">
              {/* Video header */}
              <div className="flex items-center gap-4 border-b border-slate-100 p-5">
                <button
                  onClick={() => playHit(g.hits[0])}
                  aria-label={`${g.video_title} を再生`}
                  className="group relative hidden w-36 shrink-0 cursor-pointer overflow-hidden rounded-xl sm:block"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`https://i.ytimg.com/vi/${g.youtube_id}/mqdefault.jpg`}
                    alt=""
                    loading="lazy"
                    className="aspect-video w-full object-cover transition-transform duration-300 group-hover:scale-105"
                  />
                  <span className="absolute inset-0 flex items-center justify-center bg-black/0 transition-colors duration-200 group-hover:bg-black/20">
                    <span className="flex h-9 w-9 items-center justify-center rounded-full bg-white/90 opacity-0 shadow-lg transition-opacity duration-200 group-hover:opacity-100">
                      <Play className="ml-0.5 h-4 w-4 text-teal-700" fill="currentColor" />
                    </span>
                  </span>
                </button>
                <div className="min-w-0">
                  <h2 className="text-sm font-semibold leading-snug text-slate-900">
                    {g.video_title}
                  </h2>
                  <p className="mt-1 text-xs text-slate-500">
                    {g.published_on && <span>{g.published_on} 公開 · </span>}
                    {g.hits.length} 箇所ヒット
                  </p>
                </div>
              </div>

              {/* Moment list */}
              <ul className="divide-y divide-slate-50">
                {g.hits.map((h, i) => {
                  const active =
                    playing?.youtube_id === h.youtube_id && playing?.start_sec === h.start_sec
                  return (
                    <li key={i}>
                      <button
                        onClick={() => playHit(h)}
                        className={`group flex w-full cursor-pointer items-start gap-4 p-5 text-left transition-colors duration-200 ${
                          active ? 'bg-teal-50/70' : 'hover:bg-slate-50'
                        }`}
                      >
                        <span
                          className={`mt-0.5 inline-flex shrink-0 items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-semibold tabular-nums transition-colors ${
                            active
                              ? 'bg-teal-700 text-white'
                              : 'bg-teal-50 text-teal-800 group-hover:bg-teal-100'
                          }`}
                        >
                          <Play className="h-3 w-3" fill="currentColor" />
                          {mmss(h.start_sec)}
                        </span>
                        <span className="min-w-0">
                          {h.speaker && (
                            <span className="mb-1 block text-xs font-medium text-slate-500">
                              {h.speaker}
                            </span>
                          )}
                          <span className="block text-sm leading-relaxed text-slate-800 line-clamp-3">
                            <Highlight text={h.quote} terms={terms} />
                          </span>
                        </span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            </section>
          ))}
      </div>
    </div>
  )
}
