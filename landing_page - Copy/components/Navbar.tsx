'use client';

import { motion, useScroll, useTransform } from 'framer-motion';

const NAV_ITEMS = ['Overview', 'Architecture', 'Engines', 'Security', 'Deploy'];

export default function Navbar() {
  const { scrollY } = useScroll();
  const navOpacity = useTransform(scrollY, [0, 120], [0, 1]);
  const navY = useTransform(scrollY, [0, 120], [-30, 0]);

  return (
    <motion.nav
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
          border: '1px solid rgba(255, 255, 255, 0.06)',
          pointerEvents: 'auto',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
        }}
      >
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: '#3C3489',
              boxShadow: '0 0 12px rgba(60, 52, 137, 0.6)',
            }}
          />
          <span
            style={{
              fontSize: '13px',
              fontWeight: 700,
              letterSpacing: '-0.03em',
              color: '#fff',
              textTransform: 'uppercase' as const,
            }}
          >
            SovereignAI
          </span>
        </div>

        {/* Navigation */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '36px',
          }}
        >
          {NAV_ITEMS.map((item) => (
            <a
              key={item}
              href={`#${item.toLowerCase()}`}
              style={{
                fontSize: '10px',
                fontWeight: 800,
                textTransform: 'uppercase' as const,
                letterSpacing: '0.15em',
                color: 'rgba(255, 255, 255, 0.35)',
                textDecoration: 'none',
                transition: 'color 0.4s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = '#fff')}
              onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.35)')}
            >
              {item}
            </a>
          ))}
        </div>

        {/* CTA */}
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.97 }}
          style={{
            padding: '8px 20px',
            background: '#fff',
            color: '#000',
            fontSize: '10px',
            fontWeight: 900,
            textTransform: 'uppercase' as const,
            letterSpacing: '0.15em',
            borderRadius: '9999px',
            border: 'none',
            cursor: 'pointer',
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
          Launch System
        </motion.button>
      </div>
    </motion.nav>
  );
}