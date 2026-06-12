import Hero from '@/components/home/Hero'
import ChannelIntro from '@/components/home/ChannelIntro'
import FeaturedVideos from '@/components/home/FeaturedVideos'
import CTASection from '@/components/home/CTASection'
import { SITE_URL } from '@/lib/site'

const jsonLd = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Organization',
      '@id': `${SITE_URL}/#organization`,
      name: 'The Curious Club（キュリクラ）',
      url: SITE_URL,
      logo: `${SITE_URL}/logo-icon.png`,
      sameAs: ['https://www.youtube.com/@TheCuriousClub_CC'],
    },
    {
      '@type': 'WebSite',
      '@id': `${SITE_URL}/#website`,
      name: 'The Curious Club（キュリクラ）',
      url: SITE_URL,
      inLanguage: 'ja',
      publisher: { '@id': `${SITE_URL}/#organization` },
    },
  ],
}

export default function HomePage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <Hero />
      <ChannelIntro />
      <FeaturedVideos />
      <CTASection />
    </>
  )
}
