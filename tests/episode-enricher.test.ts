import assert from 'node:assert/strict'
import test from 'node:test'
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
    <title>Short clip #shorts</title>
    <link rel="alternate" href="https://www.youtube.com/shorts/shorts001"/>
    <published>2025-01-02T00:00:00+00:00</published>
    <media:group xmlns:media="http://search.yahoo.com/mrss/">
      <media:title>Short clip #shorts</media:title>
      <media:description>Short description.</media:description>
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

test('isShort detects Shorts links, hashtags, and short durations', () => {
  assert.equal(
    isShort({ title: 'Clip', description: '', link: 'https://www.youtube.com/shorts/abc' }),
    true,
  )
  assert.equal(isShort({ title: 'Clip #shorts', description: '', link: '' }), true)
  assert.equal(isShort({ title: 'Clip', description: '', link: '', duration: 'PT2M59S' }), true)
  assert.equal(isShort({ title: 'Interview', description: '', link: '', duration: 'PT20M' }), false)
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
