// Generates the home-screen icons at build time, with no image dependency.
//
// The mark is a single dot: one thing at a time. It is drawn well inside the
// maskable safe zone so Android can crop it to any shape without clipping.

import { deflateSync } from 'node:zlib'
import { writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const GROUND = [0x14, 0x18, 0x1a]
const DOT = [0x8f, 0xe3, 0xb8]

const CRC_TABLE = (() => {
  const table = new Int32Array(256)
  for (let n = 0; n < 256; n++) {
    let c = n
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    table[n] = c
  }
  return table
})()

function crc32(buffer) {
  let c = 0xffffffff
  for (const byte of buffer) c = CRC_TABLE[(c ^ byte) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}

function chunk(type, data) {
  const length = Buffer.alloc(4)
  length.writeUInt32BE(data.length, 0)
  const body = Buffer.concat([Buffer.from(type, 'ascii'), data])
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(body), 0)
  return Buffer.concat([length, body, crc])
}

function png(size, pixels) {
  const stride = size * 3
  const raw = Buffer.alloc((stride + 1) * size)
  for (let y = 0; y < size; y++) {
    raw[y * (stride + 1)] = 0 // no per-scanline filter
    pixels.copy(raw, y * (stride + 1) + 1, y * stride, (y + 1) * stride)
  }

  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(size, 0)
  ihdr.writeUInt32BE(size, 4)
  ihdr[8] = 8 // bit depth
  ihdr[9] = 2 // truecolour RGB

  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw, { level: 9 })),
    chunk('IEND', Buffer.alloc(0)),
  ])
}

function draw(size) {
  const pixels = Buffer.alloc(size * size * 3)
  const centre = size / 2
  const radius = size * 0.17
  const samples = 3 // supersampled, so the circle edge isn't jagged

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      let inside = 0
      for (let sy = 0; sy < samples; sy++) {
        for (let sx = 0; sx < samples; sx++) {
          const px = x + (sx + 0.5) / samples
          const py = y + (sy + 0.5) / samples
          const dx = px - centre
          const dy = py - centre
          if (dx * dx + dy * dy <= radius * radius) inside++
        }
      }
      const coverage = inside / (samples * samples)
      const offset = (y * size + x) * 3
      for (let c = 0; c < 3; c++) {
        pixels[offset + c] = Math.round(GROUND[c] + (DOT[c] - GROUND[c]) * coverage)
      }
    }
  }
  return png(size, pixels)
}

const publicDir = join(dirname(fileURLToPath(import.meta.url)), '..', 'public')
for (const size of [192, 512]) {
  const file = join(publicDir, `icon-${size}.png`)
  writeFileSync(file, draw(size))
  console.log(`wrote ${file}`)
}
