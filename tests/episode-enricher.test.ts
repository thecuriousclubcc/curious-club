import assert from 'node:assert/strict'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'
import type { Video } from '../data/videos'
import { findVideosMissingEnrichment, runEpisodeEnricher } from '../scripts/episode-enricher'
import {
  appendVideosToDataFile,
  findNewLongFormEntries,
  isShort,
  parseRssEntries,
  videoFromRssEntry,
} from '../scripts/episode-enricher-core'

const rssFixture = `<?xml version="1.0" encoding="UTF-8"?>
<feed>
  <entry>
    <yt:videoId>existing01</yt:videoId>
    <title>Existing episode</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=existing01"/>
    <published>2025-01-01T00:00:00+00:00</published>
    <media:group xmlns:media="http://search.yahoo.com/mrss/">
      <media:title>Existing episode</media:title>
      <media:description>Already in data.</media:description>
    </media:group>
  </entry>
  <entry>
    <yt:videoId>shorts001</yt:videoId>
    <title>Short clip</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=shorts001"/>
    <published>2025-01-02T00:00:00+00:00</published>
    <media:group xmlns:media="http://search.yahoo.com/mrss/">
      <media:title>Short clip</media:title>
      <media:description>${'A'.repeat(240)} #ショート</media:description>
    </media:group>
  </entry>
  <entry>
    <yt:videoId>newlong01</yt:videoId>
    <title>New &amp; long episode</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=newlong01"/>
    <published>2025-01-03T00:00:00+00:00</published>
    <media:group xmlns:media="http://search.yahoo.com/mrss/">
      <media:title>New &amp; long episode</media:title>
      <media:description>Full interview.</media:description>
    </media:group>
  </entry>
</feed>`

test('findNewLongFormEntries diffs RSS against existing data and filters Shorts', () => {
  const entries = parseRssEntries(rssFixture)
  const existing = [{ id: '1', youtubeId: 'existing01' }]

  const result = findNewLongFormEntries(entries, existing)

  assert.deepEqual(
    result.map((entry) => entry.youtubeId),
    ['newlong01'],
  )
  assert.equal(result[0].title, 'New & long episode')
})

test('isShort detects creator hashtag variants in full RSS descriptions', () => {
  assert.equal(isShort({ title: 'Clip #short', description: '' }), true)
  assert.equal(isShort({ title: 'Clip', description: `${'A'.repeat(240)} #shorts` }), true)
  assert.equal(isShort({ title: 'Clip', description: `${'A'.repeat(240)} #ショート` }), true)
  assert.equal(isShort({ title: 'Interview', description: 'Full interview' }), false)
})

test('appendVideosToDataFile appends a typed Video object without touching empty updates', () => {
  const source = `export interface Video { id: string }

export const videos: Video[] = [
  {
    id: '1',
    youtubeId: 'existing01',
  },
]


export const featuredVideos = videos.filter((v) => v.featured)
`
  const entry = parseRssEntries(rssFixture).find((item) => item.youtubeId === 'newlong01')
  assert.ok(entry)

  const video = videoFromRssEntry(entry, [{ id: '1' }])
  const output = appendVideosToDataFile(source, [video])

  assert.match(output, /id: '2'/)
  assert.match(output, /youtubeId: 'newlong01'/)
  assert.equal(appendVideosToDataFile(source, []), source)
})

test('episode enricher backfills summaries after a keyless append and is idempotent', async () => {
  const cwd = mkdtempSync(join(tmpdir(), 'episode-enricher-'))
  const dataDir = join(cwd, 'data')
  const enrichmentDir = join(cwd, 'public', 'data', 'enrichments')
  mkdirSync(dataDir, { recursive: true })
  mkdirSync(enrichmentDir, { recursive: true })

  const existingVideo: Video = {
    id: '1',
    youtubeId: 'existing01',
    title: 'Existing episode',
    description: 'Already in data.',
    thumbnailUrl: 'https://img.youtube.com/vi/existing01/maxresdefault.jpg',
    youtubeUrl: 'https://www.youtube.com/watch?v=existing01',
    publishedAt: '2025-01-01',
    featured: false,
    tags: [],
  }
  const dataFilePath = join(dataDir, 'videos.ts')
  const source = `export interface Video { id: string }

export const videos: Video[] = [
  {
    id: '1',
    youtubeId: 'existing01',
  },
]

export const featuredVideos = videos.filter((v) => v.featured)
`
  writeFileSync(dataFilePath, source, 'utf-8')
  writeFileSync(join(enrichmentDir, 'existing01.json'), '{"summary":"done"}\n', 'utf-8')

  const entries = parseRssEntries(rssFixture)
  const silentLog = { log() {}, error() {} }
  const silentWrite = () => {}

  const keylessResult = await runEpisodeEnricher({
    cwd,
    dataFilePath,
    entries,
    videos: [existingVideo],
    log: silentLog,
    write: silentWrite,
  })

  assert.equal(keylessResult.exitCode, 1)
  assert.equal(keylessResult.appended, 1)
  assert.equal(keylessResult.pending, 1)
  assert.match(readFileSync(dataFilePath, 'utf-8'), /youtubeId: 'newlong01'/)
  assert.equal(existsSync(join(enrichmentDir, 'newlong01.json')), false)

  const newEntry = entries.find((entry) => entry.youtubeId === 'newlong01')
  assert.ok(newEntry)
  const appendedVideo = videoFromRssEntry(newEntry, [existingVideo])

  const keyedResult = await runEpisodeEnricher({
    cwd,
    dataFilePath,
    entries,
    videos: [existingVideo, appendedVideo],
    groqApiKey: 'test-key',
    log: silentLog,
    write: silentWrite,
    summarize: async (video) => ({
      videoId: video.youtubeId,
      summary: 'Generated summary',
      keyThemes: [],
      keyQuotes: [],
      careerInsights: [],
      suggestedQuestions: [],
      generatedAt: '2026-06-27T00:00:00.000Z',
    }),
  })

  assert.equal(keyedResult.exitCode, 0)
  assert.equal(keyedResult.appended, 0)
  assert.equal(keyedResult.enriched, 1)
  assert.equal(findVideosMissingEnrichment([existingVideo, appendedVideo], cwd).length, 0)

  const dataAfterBackfill = readFileSync(dataFilePath, 'utf-8')
  const idempotentResult = await runEpisodeEnricher({
    cwd,
    dataFilePath,
    entries,
    videos: [existingVideo, appendedVideo],
    groqApiKey: 'test-key',
    log: silentLog,
    write: silentWrite,
  })

  assert.equal(idempotentResult.exitCode, 0)
  assert.equal(idempotentResult.appended, 0)
  assert.equal(idempotentResult.enriched, 0)
  assert.equal(readFileSync(dataFilePath, 'utf-8'), dataAfterBackfill)
})
