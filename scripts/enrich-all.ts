/**
 * Batch-enrich episodes via /api/enrich (Groq). Episodes that already have an
 * enrichment JSON in public/data/enrichments/ are skipped, so it's safe to
 * re-run whenever a new episode is published. Use --force to regenerate all.
 *
 * Usage (from the curious-club directory):
 *   npx tsx scripts/enrich-all.ts [--force]
 *
 * Requires GROQ_API_KEY and ENRICH_SECRET in .env.local,
 * and the dev server running at BASE_URL (default: http://localhost:3000).
 */

// Load .env.local so the script can read ENRICH_SECRET even without a shell export
import { readFileSync } from 'fs'
import { join } from 'path'

function loadEnvLocal() {
  try {
    const content = readFileSync(join(process.cwd(), '.env.local'), 'utf-8')
    for (const line of content.split('\n')) {
      const trimmed = line.trim()
      if (!trimmed || trimmed.startsWith('#')) continue
      const eqIdx = trimmed.indexOf('=')
      if (eqIdx === -1) continue
      const key = trimmed.slice(0, eqIdx).trim()
      const val = trimmed.slice(eqIdx + 1).trim()
      if (key && val && !process.env[key]) process.env[key] = val
    }
  } catch {
    // .env.local not found — continue with existing env
  }
}

loadEnvLocal()

import { existsSync } from 'fs'
import { getAllVideos } from '../lib/videos.js'

const BASE_URL = process.env.BASE_URL ?? 'http://localhost:3000'
const SECRET = process.env.ENRICH_SECRET ?? ''
const FORCE = process.argv.includes('--force')
const ENRICHMENTS_DIR = join(process.cwd(), 'public', 'data', 'enrichments')

async function enrichOne(videoId: string, title: string, description: string) {
  const res = await fetch(`${BASE_URL}/api/enrich`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-enrich-secret': SECRET,
    },
    body: JSON.stringify({ videoId, title, description }),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status} ${text}`)
  }
  return res.json()
}

async function main() {
  if (!SECRET) {
    console.error('ENRICH_SECRET is not set. Check your .env.local.')
    process.exit(1)
  }

  // Includes episodes auto-discovered from the YouTube RSS feed
  const videos = await getAllVideos()

  const pending = FORCE
    ? videos
    : videos.filter((v) => !existsSync(join(ENRICHMENTS_DIR, `${v.youtubeId}.json`)))

  if (pending.length === 0) {
    console.log('All episodes are already enriched. Use --force to regenerate.')
    return
  }

  console.log(`Enriching ${pending.length} of ${videos.length} episodes via ${BASE_URL}/api/enrich\n`)

  for (const video of pending) {
    process.stdout.write(`[${video.id.padStart(2)}] ${video.title.slice(0, 50)}… `)
    try {
      const result = await enrichOne(video.youtubeId, video.title, video.description)
      console.log(`✓  ${result.summary?.slice(0, 55)}…`)
    } catch (err) {
      console.log(`✗  ${err}`)
    }
    await new Promise((r) => setTimeout(r, 2000))
  }

  console.log('\nDone. Enrichments saved to public/data/enrichments/')
}

main().catch(console.error)
