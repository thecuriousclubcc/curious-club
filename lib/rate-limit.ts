// Lightweight in-memory sliding-window rate limiter.
// Per-instance only (resets on redeploy / new serverless instance), which is
// enough to stop casual abuse without paying for a shared store.

interface Bucket {
  timestamps: number[]
}

const buckets = new Map<string, Bucket>()

// Periodically drop stale buckets so the map doesn't grow unbounded
const SWEEP_INTERVAL_MS = 10 * 60 * 1000
let lastSweep = Date.now()

function sweep(windowMs: number) {
  const now = Date.now()
  if (now - lastSweep < SWEEP_INTERVAL_MS) return
  lastSweep = now
  for (const [key, bucket] of buckets) {
    bucket.timestamps = bucket.timestamps.filter((t) => now - t < windowMs)
    if (bucket.timestamps.length === 0) buckets.delete(key)
  }
}

export interface RateLimitResult {
  ok: boolean
  remaining: number
}

/**
 * Returns ok: false when `key` has made more than `limit` requests
 * within the past `windowMs` milliseconds.
 */
export function rateLimit(key: string, limit: number, windowMs: number): RateLimitResult {
  sweep(windowMs)

  const now = Date.now()
  const bucket = buckets.get(key) ?? { timestamps: [] }
  bucket.timestamps = bucket.timestamps.filter((t) => now - t < windowMs)

  if (bucket.timestamps.length >= limit) {
    buckets.set(key, bucket)
    return { ok: false, remaining: 0 }
  }

  bucket.timestamps.push(now)
  buckets.set(key, bucket)
  return { ok: true, remaining: limit - bucket.timestamps.length }
}

/** Best-effort client IP from proxy headers (Vercel sets x-forwarded-for). */
export function clientIp(req: Request): string {
  const fwd = req.headers.get('x-forwarded-for')
  if (fwd) return fwd.split(',')[0].trim()
  return req.headers.get('x-real-ip') ?? 'unknown'
}
