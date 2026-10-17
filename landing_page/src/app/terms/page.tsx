import type { Metadata } from 'next'
import Link from 'next/link'

export const metadata: Metadata = {
  title: 'Terms & Conditions | SovereignAI Edge',
  description: 'Terms of use for the SovereignAI Edge website and software.',
}

export default function TermsPage() {
  return (
    <main id="main" className="doc">
      <Link href="/" className="doc-back">← SovereignAI Edge</Link>
      <h1>Terms &amp; Conditions</h1>
      <p className="doc-date">Last updated: 16 October 2026</p>
      <h2>Use of the software</h2>
      <p>
        SovereignAI Edge is provided as-is, running on your own hardware. You
        are responsible for the models you download and use, including
        complying with their licenses and acceptable-use terms, and for any
        output you generate.
      </p>
      <h2>No warranty</h2>
      <p>
        The software comes with no warranty of any kind. Do not rely on it for
        safety-critical decisions without independent verification.
      </p>
      <h2>Trademarks</h2>
      <p>
        "SovereignAI" and the SovereignAI Edge name belong to their owner. This
        site does not store or process user accounts.
      </p>
    </main>
  )
}
