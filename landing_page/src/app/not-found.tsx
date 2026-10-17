import Link from 'next/link'

export default function NotFound() {
  return (
    <main
      id="main"
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '20px',
        background: '#050505',
        textAlign: 'center',
        padding: '0 24px',
      }}
    >
      <div
        style={{
          width: '10px',
          height: '10px',
          borderRadius: '50%',
          background: '#3C3489',
          boxShadow: '0 0 24px rgba(60, 52, 137, 0.8)',
        }}
      />
      <h1 style={{ fontSize: 'clamp(3rem, 8vw, 5rem)', fontWeight: 800, letterSpacing: '-0.03em', margin: 0 }}>
        404
      </h1>
      <p style={{ fontSize: '16px', fontWeight: 300, color: 'rgba(255,255,255,0.6)', margin: 0 }}>
        This page doesn&apos;t exist. Compute stays sovereign.
      </p>
      <Link
        href="/"
        className="seq-btn"
        style={{ marginTop: '12px' }}
      >
        Back to SovereignAI Edge
      </Link>
    </main>
  )
}
