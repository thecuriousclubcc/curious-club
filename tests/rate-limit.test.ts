import { test } from 'node:test'
import assert from 'node:assert/strict'
import { rateLimit, clientIp } from '../lib/rate-limit'

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

test('allows up to the limit, then blocks', () => {
  const key = `k-${Math.random()}`
  assert.deepEqual(rateLimit(key, 2, 60_000), { ok: true, remaining: 1 })
  assert.deepEqual(rateLimit(key, 2, 60_000), { ok: true, remaining: 0 })
  assert.deepEqual(rateLimit(key, 2, 60_000), { ok: false, remaining: 0 })
})

test('keys are isolated from each other', () => {
  const a = `a-${Math.random()}`
  const b = `b-${Math.random()}`
  rateLimit(a, 1, 60_000)
  assert.equal(rateLimit(a, 1, 60_000).ok, false)
  assert.equal(rateLimit(b, 1, 60_000).ok, true)
})

test('window expiry frees the budget again', async () => {
  const key = `w-${Math.random()}`
  assert.equal(rateLimit(key, 1, 50).ok, true)
  assert.equal(rateLimit(key, 1, 50).ok, false)
  await sleep(60)
  assert.equal(rateLimit(key, 1, 50).ok, true)
})

test('a blocked request does not consume window budget', async () => {
  const key = `nb-${Math.random()}`
  assert.equal(rateLimit(key, 1, 100).ok, true)
  await sleep(60)
  // blocked attempt inside the window must not extend/refill anything
  assert.equal(rateLimit(key, 1, 100).ok, false)
  await sleep(60)
  // first request is now outside the 100ms window -> allowed again
  assert.equal(rateLimit(key, 1, 100).ok, true)
})

test('clientIp prefers first x-forwarded-for hop', () => {
  const req = new Request('http://x', {
    headers: { 'x-forwarded-for': '203.0.113.7, 10.0.0.1', 'x-real-ip': '10.0.0.9' },
  })
  assert.equal(clientIp(req), '203.0.113.7')
})

test('clientIp falls back to x-real-ip, then unknown', () => {
  assert.equal(
    clientIp(new Request('http://x', { headers: { 'x-real-ip': '198.51.100.2' } })),
    '198.51.100.2'
  )
  assert.equal(clientIp(new Request('http://x')), 'unknown')
})
