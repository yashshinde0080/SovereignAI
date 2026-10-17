'use client';

import { motion, useScroll, useTransform } from 'framer-motion';

const REPO_URL = 'https://github.com/yashshinde0080/SovereignAI';

const NAV_ITEMS = [
  { label: 'Overview', href: '#overview' },
  { label: 'Engines', href: '#engines' },
  { label: 'Architecture', href: '#architecture' },
  { label: 'Security', href: '#security' },
  { label: 'Deploy', href: '#deploy' },
];

export default function Navbar() {
  const { scrollY } = useScroll();
  const navOpacity = useTransform(scrollY, [0, 120], [0, 1]);
  const navY = useTransform(scrollY, [0, 120], [-30, 0]);

  return (
    <motion.nav
      aria-label="Primary"
      style={{
        position: 'fixed',
        top: '24px',
        left: 0,
        right: 0,
        zIndex: 100,
        padding: '0 24px',
        pointerEvents: 'none',
        opacity: navOpacity,
        y: navY,
      }}
    >
      <div
        style={{
          maxWidth: '1000px',
          margin: '0 auto',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 32px',
          borderRadius: '9999px',
          background: 'rgba(10, 10, 12, 0.6)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          pointerEvents: 'auto',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
        }}
      >
        {/* Brand */}
        <a
          href="#overview"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            textDecoration: 'none',
          }}
        >
          <span
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: '#3C3489',
              boxShadow: '0 0 12px rgba(60, 52, 137, 0.8)',
            }}
          />
          <span
            style={{
              fontSize: '13px',
              fontWeight: 700,
              letterSpacing: '-0.02em',
              color: '#fff',
              textTransform: 'uppercase',
            }}
          >
            SovereignAI
          </span>
        </a>

        {/* Navigation */}
        <div className="nav-links">
          {NAV_ITEMS.map((item) => (
            <a
              key={item.label}
              href={item.href}
              style={{
                fontSize: '10px',
                fontWeight: 800,
                textTransform: 'uppercase',
                letterSpacing: '0.15em',
                color: 'rgba(255, 255, 255, 0.6)',
                textDecoration: 'none',
                transition: 'color 0.4s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = '#fff')}
              onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.6)')}
            >
              {item.label}
            </a>
          ))}
        </div>

        {/* CTA */}
        <motion.a
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.97 }}
          href={REPO_URL}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            padding: '8px 20px',
            background: '#fff',
            color: '#000',
            fontSize: '10px',
            fontWeight: 900,
            textTransform: 'uppercase',
            letterSpacing: '0.15em',
            borderRadius: '9999px',
            textDecoration: 'none',
            transition: 'all 0.4s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = '#3C3489';
            e.currentTarget.style.color = '#fff';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = '#fff';
            e.currentTarget.style.color = '#000';
          }}
        >
          View on GitHub
        </motion.a>
      </div>
    </motion.nav>
  );
}
