'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { Search, X, Loader2 } from 'lucide-react'
import type { Video } from '@/data/videos'
import VideoCard from '@/components/videos/VideoCard'

interface Props {
  videos: Video[]
}

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debounced
}

export default function VideoSearchBar({ videos }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Video[]>(videos)
  const [loading, setLoading] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [activeTag, setActiveTag] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const debouncedQuery = useDebounce(query, 500)

  // Collect all unique tags from videos
  const allTags = Array.from(new Set(videos.flatMap((v) => v.tags))).slice(0, 12)

  const search = useCallback(
    async (q: string) => {
      if (abortRef.current) abortRef.current.abort()
      abortRef.current = new AbortController()

      if (!q.trim()) {
        setResults(activeTag ? videos.filter((v) => v.tags.includes(activeTag)) : videos)
        setHasSearched(false)
        return
      }

      setLoading(true)
      setHasSearched(true)
      try {
        const res = await fetch(
          `/api/search?q=${encodeURIComponent(q)}`,
          { signal: abortRef.current.signal },
        )
        if (res.ok) {
          const data = await res.json()
          setResults(data.results as Video[])
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name !== 'AbortError') {
          // Fall back to basic title match on error
          const lower = q.toLowerCase()
          setResults(videos.filter((v) =>
            v.title.toLowerCase().includes(lower) ||
            v.description.toLowerCase().includes(lower),
          ))
        }
      } finally {
        setLoading(false)
      }
    },
    [videos, activeTag],
  )

  useEffect(() => {
    search(debouncedQuery)
  }, [debouncedQuery, search])

  // Tag filter (client-side, no AI)
  useEffect(() => {
    if (!query.trim()) {
      setResults(activeTag ? videos.filter((v) => v.tags.includes(activeTag)) : videos)
    }
  }, [activeTag, videos, query])

  const clearSearch = () => {
    setQuery('')
    setActiveTag(null)
    setResults(videos)
    setHasSearched(false)
  }

  return (
    <div>
      {/* Search input */}
      <div className="relative mb-6">
        <Search
          size={16}
          className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"
        />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="キャリア、医療、起業… AIで意味検索"
          className="w-full pl-11 pr-10 py-3 rounded-xl bg-white border border-slate-200 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent shadow-sm"
        />
        {loading && (
          <Loader2
            size={16}
            className="absolute right-4 top-1/2 -translate-y-1/2 text-teal-500 animate-spin"
          />
        )}
        {!loading && (query || activeTag) && (
          <button
            onClick={clearSearch}
            className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
          >
            <X size={16} />
          </button>
        )}
      </div>

      {/* Tag pills */}
      <div className="flex gap-2 flex-wrap mb-8">
        {allTags.map((tag) => (
          <button
            key={tag}
            onClick={() => setActiveTag(activeTag === tag ? null : tag)}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
              activeTag === tag
                ? 'bg-teal-700 text-white border-teal-700'
                : 'bg-white text-slate-600 border-slate-200 hover:border-teal-400 hover:text-teal-700'
            }`}
          >
            {tag}
          </button>
        ))}
      </div>

      {/* Results */}
      {hasSearched && !loading && results.length === 0 ? (
        <div className="text-center py-20 text-slate-400 text-sm">
          「{query}」に関連するエピソードは見つかりませんでした。
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {results.map((video) => (
            <VideoCard key={video.id} video={video} />
          ))}
        </div>
      )}
    </div>
  )
}
