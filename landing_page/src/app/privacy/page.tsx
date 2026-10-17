import type { Metadata } from 'next'
import Link from 'next/link'

export const metadata: Metadata = {
  title: 'Privacy Policy | SovereignAI Edge',
  description: 'How the SovereignAI Edge website handles data: it does not.',
}

export default function PrivacyPage() {
  return (
    <main id="main" className="doc">
      <Link href="/" className="doc-back">← SovereignAI Edge</Link>
      <h1>Privacy Policy</h1>
      <p className="doc-date">Last updated: 16 October 2026</p>
      <p>
        SovereignAI Edge is local-first software. This website sets no cookies,
        runs no trackers or analytics, and collects no personal data. Pages are
        served as static content; we do not ask for your name, email, or
        payment details.
      </p>
      <h2>If you run SovereignAI Edge</h2>
      <p>
        The application runs entirely on your hardware. It has zero telemetry:
        no usage data, prompts, models, or files ever leave your machine unless
        you explicitly configure a cloud provider API and make a request
        through it. In that case, the provider's own privacy policy applies to
        the requests you send them.
      </p>
      <h2>Questions</h2>
      <p>
        Open an issue at{' '}
        <a href="https://github.com/yashshinde0080/SovereignAI" target="_blank" rel="noopener noreferrer">
          github.com/yashshinde0080/SovereignAI
        </a>.
      </p>
    </main>
  )
}
