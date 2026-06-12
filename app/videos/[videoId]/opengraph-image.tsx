import { ImageResponse } from 'next/og'
import { videos as staticVideos } from '@/data/videos'

export const runtime = 'edge'
export const size = { width: 1200, height: 630 }
export const contentType = 'image/png'

export default async function OGImage({
  params,
}: {
  params: Promise<{ videoId: string }>
}) {
  const { videoId } = await params
  const video = staticVideos.find((v) => v.youtubeId === videoId)

  const title = video?.title ?? 'The Curious Club'
  const thumbnailUrl = `https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`

  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          position: 'relative',
          backgroundColor: '#0f172a',
        }}
      >
        {/* Background thumbnail */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={thumbnailUrl}
          alt=""
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            opacity: 0.35,
          }}
        />

        {/* Gradient overlay */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background:
              'linear-gradient(to top, rgba(15,23,42,0.95) 40%, rgba(15,23,42,0.4) 100%)',
          }}
        />

        {/* Content */}
        <div
          style={{
            position: 'relative',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'flex-end',
            padding: '60px 72px',
            width: '100%',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              marginBottom: 20,
            }}
          >
            <div
              style={{
                backgroundColor: '#0d9488',
                borderRadius: 999,
                padding: '4px 16px',
                fontSize: 13,
                color: 'white',
                letterSpacing: '0.1em',
              }}
            >
              Interview
            </div>
          </div>

          <div
            style={{
              fontSize: title.length > 40 ? 36 : 44,
              fontWeight: 700,
              color: 'white',
              lineHeight: 1.3,
              marginBottom: 24,
              maxWidth: 900,
            }}
          >
            {title}
          </div>

          <div
            style={{
              fontSize: 18,
              color: 'rgba(255,255,255,0.6)',
              letterSpacing: '0.05em',
            }}
          >
            The Curious Club（キュリクラ）
          </div>
        </div>
      </div>
    ),
    { ...size },
  )
}
