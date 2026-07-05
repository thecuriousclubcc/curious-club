// X (Twitter) poster — consumes approved drafts from the review queue and posts.
//
// Build step 2 of the X automation plan (see harness `playbooks/x-marketing.md`).
// Reads `data/x-queue.json`, takes drafts with `status: "approved"`, and for each:
//   1. uploads the native video (draft.mediaPath) if present,
//   2. posts launchPost (with the video attached),
//   3. posts linkReply as a reply (carries the YouTube link),
//   4. posts the thread, chained off the launch post,
//   5. marks the draft `status: "posted"` and records the tweet ids.
//
// SAFETY: dry-run by default. It prints exactly what it WOULD post and changes
// nothing. Pass --post to actually publish. Only `approved` drafts are ever sent,
// so a human stays in the loop (per ../invariants of the harness).
//
// Usage:
//   npm run x:post                 # dry-run: show what approved drafts would post
//   npm run x:post -- --post       # actually publish approved drafts
//   npm run x:post -- --id=<ytId>  # limit to one draft
//   npm run x:post -- --post --id=<ytId>
//
// Env (OAuth 1.0a user context — required only for --post):
//   X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET

import { existsSync, readFileSync } from 'fs'
import { readFile, writeFile } from 'fs/promises'
import path from 'path'
import { fileURLToPath } from 'url'
import { EUploadMimeType, TwitterApi } from 'twitter-api-v2'
import { loadQueue, type XQueue, type XSyndicationDraft } from './x-syndicate'

const QUEUE_PATH = path.join('data', 'x-queue.json')

function loadEnvLocal() {
  try {
    const content = readFileSync(path.join(process.cwd(), '.env.local'), 'utf-8')
    for (const line of content.split('\n')) {
      const trimmed = line.trim()
      if (!trimmed || trimmed.startsWith('#')) continue
      const eqIdx = trimmed.indexOf('=')
      if (eqIdx === -1) continue
      const key = trimmed.slice(0, eqIdx).trim()
      const value = trimmed.slice(eqIdx + 1).trim().replace(/^['"]|['"]$/g, '')
      if (key && value && !process.env[key]) process.env[key] = value
    }
  } catch {
    // .env.local is optional (dry-run needs no credentials).
  }
}

function getClient(): TwitterApi {
  const appKey = process.env.X_API_KEY
  const appSecret = process.env.X_API_SECRET
  const accessToken = process.env.X_ACCESS_TOKEN
  const accessSecret = process.env.X_ACCESS_SECRET
  if (!appKey || !appSecret || !accessToken || !accessSecret) {
    throw new Error(
      'MISSING X credentials. Set X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET to post.',
    )
  }
  return new TwitterApi({ appKey, appSecret, accessToken, accessSecret })
}

function describe(draft: XSyndicationDraft): string {
  const lines = [
    `--- ${draft.youtubeId} — ${draft.videoTitle}`,
    `  [1] launchPost${draft.mediaPath ? ` (+video: ${draft.mediaPath})` : ' (text-only)'}: ${draft.launchPost}`,
    `  [2] reply        : ${draft.linkReply}`,
  ]
  draft.thread.forEach((t, i) => lines.push(`  [${i + 3}] thread ${i + 1}    : ${t}`))
  return lines.join('\n')
}

interface PostResult {
  launchId: string
  replyId: string
  threadIds: string[]
}

async function postDraft(client: TwitterApi, draft: XSyndicationDraft): Promise<PostResult> {
  const rw = client.readWrite

  // 1. Upload native video, if a real file is present.
  let mediaId: string | undefined
  if (draft.mediaPath && existsSync(draft.mediaPath)) {
    mediaId = await rw.v1.uploadMedia(draft.mediaPath, {
      mimeType: EUploadMimeType.Mp4,
      target: 'tweet',
    })
  }

  // 2. Launch post (native video attached when available).
  const launch = await rw.v2.tweet(
    draft.launchPost,
    mediaId ? { media: { media_ids: [mediaId] } } : {},
  )
  const launchId = launch.data.id

  // 3. Link reply (keeps the link out of the main post).
  const reply = await rw.v2.tweet(draft.linkReply, {
    reply: { in_reply_to_tweet_id: launchId },
  })
  const replyId = reply.data.id

  // 4. Thread, chained off the launch post.
  const threadIds: string[] = []
  let prevId = launchId
  for (const text of draft.thread) {
    const t = await rw.v2.tweet(text, { reply: { in_reply_to_tweet_id: prevId } })
    threadIds.push(t.data.id)
    prevId = t.data.id
  }

  return { launchId, replyId, threadIds }
}

async function saveQueue(queue: XQueue, queuePath = QUEUE_PATH) {
  queue.updated = new Date().toISOString()
  await writeFile(queuePath, `${JSON.stringify(queue, null, 2)}\n`, 'utf-8')
}

interface RunOptions {
  post?: boolean
  id?: string
  queuePath?: string
  log?: Pick<Console, 'log' | 'error'>
}

export async function runXPost(options: RunOptions = {}) {
  const log = options.log ?? console
  const queuePath = options.queuePath ?? QUEUE_PATH

  const queue = await loadQueue(queuePath)
  let approved = queue.drafts.filter((d) => d.status === 'approved')
  if (options.id) approved = approved.filter((d) => d.youtubeId === options.id)

  if (approved.length === 0) {
    log.log('OK: no drafts with status "approved" to post. (Set status in data/x-queue.json.)')
    return { posted: 0, exitCode: 0 }
  }

  if (!options.post) {
    log.log(`DRY RUN — ${approved.length} approved draft(s) would post (pass --post to publish):\n`)
    for (const draft of approved) log.log(describe(draft))
    log.log('\nNothing was posted. Re-run with --post to publish.')
    return { posted: 0, exitCode: 0 }
  }

  const client = getClient()
  let posted = 0
  for (const draft of approved) {
    log.log(`Posting ${draft.youtubeId} ${draft.videoTitle.slice(0, 48)}...`)
    try {
      const result = await postDraft(client, draft)
      draft.status = 'posted'
      // Stash ids for later metrics without changing the draft's shape contract.
      ;(draft as XSyndicationDraft & { postedIds?: PostResult }).postedIds = result
      posted += 1
      log.log(`  OK https://x.com/i/web/status/${result.launchId}`)
      await saveQueue(queue, queuePath) // persist after each, so a mid-run failure isn't lost
    } catch (error) {
      log.error(`  FAILED: ${error instanceof Error ? error.message : error}`)
      return { posted, exitCode: 1 }
    }
  }

  log.log(`OK: posted ${posted} draft(s).`)
  return { posted, exitCode: 0 }
}

function parseArgs(argv: string[]): RunOptions {
  const opts: RunOptions = {}
  for (const arg of argv) {
    if (arg === '--post') opts.post = true
    else if (arg.startsWith('--id=')) opts.id = arg.slice('--id='.length)
  }
  return opts
}

async function main() {
  loadEnvLocal()
  const result = await runXPost(parseArgs(process.argv.slice(2)))
  if (result.exitCode !== 0) process.exit(result.exitCode)
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : error)
    process.exit(1)
  })
}
