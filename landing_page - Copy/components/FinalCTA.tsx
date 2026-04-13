'use client';

import { motion } from 'framer-motion';

export default function FinalCTA() {
  return (
    <section
      id="deploy"
      style={{
        position: 'relative',
        padding: '200px 32px',
        background: '#050505',
        overflow: 'hidden',
      }}
    >
      {/* Volumetric background glow */}
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: '1000px',
          height: '500px',
          background: 'radial-gradient(ellipse, rgba(60, 52, 137, 0.12) 0%, transparent 70%)',
          pointerEvents: 'none',
        }}
      />

      {/* Content */}
      <div style={{ maxWidth: '900px', margin: '0 auto', textAlign: 'center', position: 'relative', zIndex: 10 }}>
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 1.2 }}
          viewport={{ once: true }}
        >
          <p
            style={{
              fontSize: '10px',
              fontWeight: 900,
              letterSpacing: '0.25em',
              textTransform: 'uppercase' as const,
              color: '#1D9E75',
              marginBottom: '32px',
            }}
          >
            Available Now
          </p>

          <h2
            className="text-gradient"
            style={{
              fontSize: 'clamp(4rem, 10vw, 9rem)',
              fontWeight: 800,
              letterSpacing: '-0.06em',
              lineHeight: 0.9,
              marginBottom: '12px',
            }}
          >
            Run AI
          </h2>
          <h2
            style={{
              fontSize: 'clamp(4rem, 10vw, 9rem)',
              fontWeight: 200,
              fontStyle: 'italic',
              letterSpacing: '-0.06em',
              lineHeight: 0.9,
              color: 'rgba(255,255,255,0.12)',
              marginBottom: '48px',
            }}
          >
            anywhere.
          </h2>

          <p
            style={{
              fontSize: 'clamp(16px, 2vw, 22px)',
              fontWeight: 300,
              color: 'rgba(255,255,255,0.35)',
              maxWidth: '480px',
              margin: '0 auto 56px',
              lineHeight: 1.6,
            }}
          >
            Sovereign compute. No compromises. Zero latency hardware-native execution.
          </p>

          {/* CTA Button */}
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.97 }}
            style={{
              padding: '20px 56px',
              background: '#fff',
              color: '#000',
              fontSize: '11px',
              fontWeight: 900,
              textTransform: 'uppercase' as const,
              letterSpacing: '0.15em',
              borderRadius: '9999px',
              border: 'none',
              cursor: 'pointer',
              boxShadow: '0 0 60px rgba(255,255,255,0.1), 0 25px 50px rgba(0,0,0,0.5)',
              transition: 'all 0.5s ease',
              position: 'relative' as const,
              overflow: 'hidden',
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
            Deploy SovereignAI Edge
          </motion.button>
        </motion.div>
      </div>

      {/* Footer */}
      <motion.footer
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        transition={{ duration: 1, delay: 0.5 }}
        viewport={{ once: true }}
        style={{
          maxWidth: '1200px',
          margin: '200px auto 0',
          paddingTop: '40px',
          borderTop: '1px solid rgba(255,255,255,0.03)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap' as const,
          gap: '24px',
        }}
      >
        <p
          style={{
            fontSize: '10px',
            fontWeight: 800,
            letterSpacing: '0.15em',
            textTransform: 'uppercase' as const,
            color: 'rgba(255,255,255,0.08)',
          }}
        >
          © 2025 SovereignAI Infrastructure
        </p>
        <div style={{ display: 'flex', gap: '40px' }}>
          {['Documentation', 'Security Audit', 'Contact'].map((link) => (
            <a
              key={link}
              href="#"
              style={{
                fontSize: '10px',
                fontWeight: 800,
                letterSpacing: '0.15em',
                textTransform: 'uppercase' as const,
                color: 'rgba(255,255,255,0.08)',
                textDecoration: 'none',
                transition: 'color 0.4s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = '#fff')}
              onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.08)')}
            >
              {link}
            </a>
          ))}
        </div>
        <p
          style={{
            fontSize: '10px',
            fontWeight: 800,
            letterSpacing: '0.15em',
            textTransform: 'uppercase' as const,
            color: 'rgba(255,255,255,0.08)',
          }}
        >
          Built for Sovereignty
        </p>
      </motion.footer>
    </section>
  );
}