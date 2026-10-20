import Link from 'next/link'

export default function Footer() {
  return (
    <footer
      style={{
        position: 'relative',
        zIndex: 2,
        background: '#050505',
        borderTop: '1px solid rgba(255,255,255,0.08)',
        padding: '28px 24px',
      }}
    >
      <div
        style={{
          maxWidth: '1000px',
          margin: '0 auto',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '16px',
          flexWrap: 'wrap',
        }}
      >
        <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.55)' }}>
          © {new Date().getFullYear()} SovereignAI Edge
        </span>
        <nav aria-label="Footer" style={{ display: 'flex', gap: '28px' }}>
          <Link href="/privacy" className="footer-link">Privacy</Link>
          <Link href="/terms" className="footer-link">Terms</Link>
          <a
            href="https://github.com/yashshinde0080/SovereignAI"
            target="_blank"
            rel="noopener noreferrer"
            className="footer-link"
          >
            GitHub
          </a>
        </nav>
      </div>
    </footer>
  )
}
