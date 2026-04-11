'use client';

import { motion } from 'framer-motion';

const MODULES = [
  { label: 'COMPUTE CORES', desc: 'Multi-threaded tensor processing across all available CPU cores.', color: '#3C3489' },
  { label: 'MEMORY LAYERS', desc: 'Dynamic layer streaming from disk—storage becomes compute.', color: '#1D9E75' },
  { label: 'KV CACHE', desc: 'Intelligent attention state management for context retention.', color: '#3C3489' },
  { label: 'PIPELINE', desc: 'Zero-copy data flow architecture with minimal overhead.', color: '#1D9E75' },
];

export default function ArchitectureSection() {
  return (
    <section
      id="architecture"
      style={{
        position: 'relative',
        padding: '200px 32px',
        background: '#050505',
      }}
    >
      <div style={{ maxWidth: '1100px', margin: '0 auto' }}>
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 1 }}
          viewport={{ once: true }}
          style={{ textAlign: 'center', marginBottom: '100px' }}
        >
          <p
            style={{
              fontSize: '10px',
              fontWeight: 900,
              letterSpacing: '0.25em',
              textTransform: 'uppercase' as const,
              color: 'rgba(255,255,255,0.2)',
              marginBottom: '20px',
            }}
          >
            System Architecture
          </p>
          <h2
            className="text-gradient"
            style={{
              fontSize: 'clamp(3rem, 7vw, 7rem)',
              fontWeight: 800,
              letterSpacing: '-0.05em',
              lineHeight: 1,
              marginBottom: '32px',
            }}
          >
            Built for constraint.
          </h2>
          <p
            style={{
              fontSize: 'clamp(16px, 2vw, 22px)',
              fontWeight: 300,
              color: 'rgba(255,255,255,0.3)',
              maxWidth: '560px',
              margin: '0 auto',
              lineHeight: 1.6,
            }}
          >
            Memory is not a limitation. Storage becomes compute.
          </p>
        </motion.div>

        {/* Module Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
          {MODULES.map((item, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: i * 0.08 }}
              viewport={{ once: true }}
              style={{
                padding: '48px',
                background: 'rgba(10, 10, 12, 0.4)',
                borderRadius: '32px',
                border: '1px solid rgba(255,255,255,0.03)',
                transition: 'border-color 0.6s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = `${item.color}33`)}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.03)')}
            >
              {/* Top row */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '32px' }}>
                <span
                  style={{
                    padding: '4px 12px',
                    borderRadius: '9999px',
                    background: `${item.color}15`,
                    color: item.color,
                    fontSize: '9px',
                    fontWeight: 900,
                    letterSpacing: '0.15em',
                    textTransform: 'uppercase' as const,
                  }}
                >
                  Module {i + 1}
                </span>
                <div
                  style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    background: item.color,
                    boxShadow: `0 0 10px ${item.color}80`,
                    animation: 'pulse 2s infinite',
                  }}
                />
              </div>

              <h3 style={{ fontSize: '22px', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '12px' }}>
                {item.label}
              </h3>
              <p style={{ fontSize: '14px', fontWeight: 400, color: 'rgba(255,255,255,0.3)', lineHeight: 1.7 }}>
                {item.desc}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}