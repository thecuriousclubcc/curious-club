import Hero from '@/components/home/Hero'
import ChannelIntro from '@/components/home/ChannelIntro'
import FeaturedVideos from '@/components/home/FeaturedVideos'
import CTASection from '@/components/home/CTASection'

export default function HomePage() {
  return (
    <>
      <Hero />
      <ChannelIntro />
      <FeaturedVideos />
      <CTASection />
    </>
  )
}
