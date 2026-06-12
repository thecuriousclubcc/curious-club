'use client'

import { useState } from 'react'
import Image from 'next/image'

interface Props {
  src: string
  alt: string
}

// YouTube serves maxresdefault.jpg only for some videos; fall back to
// hqdefault.jpg (always available) when it 404s.
export default function VideoThumbnail({ src, alt }: Props) {
  const [currentSrc, setCurrentSrc] = useState(src)

  return (
    <Image
      src={currentSrc}
      alt={alt}
      fill
      sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
      className="object-cover group-hover:scale-105 transition-transform duration-500"
      onError={() => {
        const fallback = currentSrc.replace('maxresdefault', 'hqdefault')
        if (fallback !== currentSrc) setCurrentSrc(fallback)
      }}
    />
  )
}
