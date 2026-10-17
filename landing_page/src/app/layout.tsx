import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { SITE_URL } from '@/lib/site'

const inter = Inter({ 
  subsets: ['latin'],
  variable: '--font-inter',
})

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: 'SovereignAI Edge | AI Infrastructure Without Dependency',
  description: 'Portable, offline-first AI compute infrastructure. Run LLMs locally without cloud dependency.',
  keywords: ['AI', 'Infrastructure', 'Offline AI', 'Edge Computing', 'Sovereign Compute'],
  openGraph: {
    title: 'SovereignAI Edge | AI Infrastructure Without Dependency',
    description: 'Portable, offline-first AI compute infrastructure. Run LLMs locally without cloud dependency.',
    url: '/',
    siteName: 'SovereignAI Edge',
    type: 'website',
    images: [{ url: '/frames/frame-001.jpg', width: 1920, height: 1080, alt: 'SovereignAI Edge device' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'SovereignAI Edge | AI Infrastructure Without Dependency',
    description: 'Portable, offline-first AI compute infrastructure. Run LLMs locally without cloud dependency.',
    images: ['/frames/frame-001.jpg'],
  },
  robots: { index: true, follow: true },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body style={{ background: '#050505', color: '#fff', minHeight: '100vh' }} suppressHydrationWarning>
        <a href="#main" className="skip-link">Skip to content</a>
        {children}
      </body>
    </html>
  )
}
