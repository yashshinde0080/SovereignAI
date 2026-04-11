'use client';

import { motion } from 'framer-motion';

const SECURITY_ITEMS = [
  { title: 'Offline-First', desc: 'No internet required. Ever.' },
  { title: 'Zero Telemetry', desc: 'Nothing tracked. Nothing sent.' },
  { title: 'Air-Gapped', desc: 'Runs in complete isolation.' },
];

export default function SecuritySection() {
  return (
    <section
      id="security"
      style={{
        position: 'relative',
        padding: '200px 32px',
        background: '#050505',
      }}
    >
      <div style={{ maxWidth: '1000px', margin: '0 auto', textAlign: 'center' }}>
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 1 }}
          viewport={{ once: true }}
        >
          {/* Badge */}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '10px',
              padding: '6px 16px',
              borderRadius: '9999px',
              background: 'rgba(29, 158, 117, 0.08)',
              border: '1px solid rgba(29, 158, 117, 0.2)',
              marginBottom: '48px',
            }}
          >
            <div
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                background: '#1D9E75',
                boxShadow: '0 0 8px rgba(29, 158, 117, 0.6)',
                animation: 'pulse 2s infinite',
              }}
            />
            <span
              style={{
                fontSize: '9px',
                fontWeight: 900,
                letterSpacing: '0.15em',
                textTransform: 'uppercase' as const,
                color: '#1D9E75',
              }}
            >
              Security Verified
            </span>
          </div>

          {/* Heading */}
          <h2
            className="text-gradient"
            style={{
              fontSize: 'clamp(3rem, 7vw, 7rem)',
              fontWeight: 800,
              letterSpacing: '-0.05em',
              lineHeight: 1,
              marginBottom: '12px',
            }}
          >
            Nothing leaves
          </h2>
          <h2
            style={{
              fontSize: 'clamp(3rem, 7vw, 7rem)',
              fontWeight: 200,
              fontStyle: 'italic',
              letterSpacing: '-0.05em',
              lineHeight: 1,
              color: 'rgba(255,255,255,0.15)',
              marginBottom: '48px',
            }}
          >
            the machine.
          </h2>

          <p
            style={{
              fontSize: 'clamp(16px, 2vw, 22px)',
              fontWeight: 300,
              color: 'rgba(255,255,255,0.35)',
              maxWidth: '560px',
              margin: '0 auto 80px',
              lineHeight: 1.6,
            }}
          >
            Air-gapped capable. Zero telemetry. Absolute compute sovereignty.
          </p>

          {/* Security Grid */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '48px',
              textAlign: 'left',
            }}
          >
            {SECURITY_ITEMS.map((item, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, delay: i * 0.1 }}
                viewport={{ once: true }}
                style={{
                  paddingTop: '40px',
                  borderTop: '1px solid rgba(255,255,255,0.04)',
                  position: 'relative',
                  overflow: 'hidden',
                }}
                onMouseEnter={(e) => {
                  const line = e.currentTarget.querySelector('.hover-line') as HTMLElement;
                  if (line) line.style.width = '100%';
                }}
                onMouseLeave={(e) => {
                  const line = e.currentTarget.querySelector('.hover-line') as HTMLElement;
                  if (line) line.style.width = '0';
                }}
              >
                {/* Hover accent line */}
                <div
                  className="hover-line"
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '0',
                    height: '1px',
                    background: '#1D9E75',
                    transition: 'width 0.6s ease',
                  }}
                />
                <p
                  style={{
                    fontSize: '10px',
                    fontWeight: 900,
                    letterSpacing: '0.15em',
                    textTransform: 'uppercase' as const,
                    color: 'rgba(255,255,255,0.35)',
                    marginBottom: '12px',
                  }}
                >
                  {item.title}
                </p>
                <p style={{ fontSize: '20px', fontWeight: 700, letterSpacing: '-0.02em' }}>
                  {item.desc}
                </p>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  );
}