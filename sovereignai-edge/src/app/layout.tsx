import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ 
  subsets: ['latin'],
  variable: '--font-inter',
})

export const metadata: Metadata = {
  title: 'SovereignAI Edge | AI Infrastructure Without Dependency',
  description: 'Portable, offline-first AI compute infrastructure. Run LLMs locally without cloud dependency.',
  keywords: ['AI', 'Infrastructure', 'Offline AI', 'Edge Computing', 'Sovereign Compute'],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="antialiased">
        {children}
      </body>
    </html>
  )
}