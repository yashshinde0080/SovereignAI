'use client';

import { motion } from 'framer-motion';

const FEATURES_FULLRAM = ['Instant token generation', 'No streaming overhead', 'Hardware-native execution'];
const FEATURES_LAYER = ['Minimal RAM footprint', 'SSD/USB-based execution', 'Dynamic paging system'];

export default function EngineSection() {
  return (
    <section
      id="engines"
      style={{
        position: 'relative',
        padding: '200px 32px',
        background: '#050505',
      }}
    >
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
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
              color: '#1D9E75',
              marginBottom: '20px',
            }}
          >
            Dual Execution
          </p>
          <h2
            className="text-gradient"
            style={{
              fontSize: 'clamp(3rem, 7vw, 7rem)',
              fontWeight: 800,
              letterSpacing: '-0.05em',
              lineHeight: 1,
            }}
          >
            Dual execution.
          </h2>
          <h2
            style={{
              fontSize: 'clamp(3rem, 7vw, 7rem)',
              fontWeight: 800,
              letterSpacing: '-0.05em',
              lineHeight: 1,
              color: 'rgba(255,255,255,0.15)',
            }}
          >
            One system.
          </h2>
        </motion.div>

        {/* Cards Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '16px' }}>
          {/* FullRAM Card */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            viewport={{ once: true }}
            style={{
              padding: '56px',
              background: 'rgba(10, 10, 12, 0.5)',
              borderRadius: '32px',
              border: '1px solid rgba(255,255,255,0.03)',
              transition: 'border-color 0.6s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'rgba(60, 52, 137, 0.3)')}
            onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.03)')}
          >
            {/* Badge */}
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 16px',
                borderRadius: '9999px',
                background: 'rgba(60, 52, 137, 0.1)',
                border: '1px solid rgba(60, 52, 137, 0.2)',
                marginBottom: '40px',
              }}
            >
              <div
                style={{
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  background: '#3C3489',
                  boxShadow: '0 0 8px rgba(60, 52, 137, 0.6)',
                }}
              />
              <span
                style={{
                  fontSize: '9px',
                  fontWeight: 900,
                  letterSpacing: '0.15em',
                  textTransform: 'uppercase' as const,
                  color: '#3C3489',
                }}
              >
                Performance Mode
              </span>
            </div>

            <h3 style={{ fontSize: '48px', fontWeight: 800, letterSpacing: '-0.04em', marginBottom: '24px' }}>
              FullRAM
            </h3>
            <p style={{ fontSize: '18px', fontWeight: 300, color: 'rgba(255,255,255,0.35)', lineHeight: 1.7, marginBottom: '40px', maxWidth: '380px' }}>
              Maximum performance mode. Entire model loaded into system memory. Zero latency. Direct silicon access.
            </p>

            {/* Features */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {FEATURES_FULLRAM.map((feat) => (
                <div key={feat} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{ width: '4px', height: '4px', borderRadius: '50%', background: '#3C3489' }} />
                  <span
                    style={{
                      fontSize: '10px',
                      fontWeight: 800,
                      letterSpacing: '0.15em',
                      textTransform: 'uppercase' as const,
                      color: 'rgba(255,255,255,0.2)',
                    }}
                  >
                    {feat}
                  </span>
                </div>
              ))}
            </div>
          </motion.div>

          {/* LayerStream Card */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.15 }}
            viewport={{ once: true }}
            style={{
              padding: '56px',
              background: 'rgba(10, 10, 12, 0.5)',
              borderRadius: '32px',
              border: '1px solid rgba(255,255,255,0.03)',
              transition: 'border-color 0.6s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'rgba(29, 158, 117, 0.3)')}
            onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.03)')}
          >
            {/* Badge */}
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 16px',
                borderRadius: '9999px',
                background: 'rgba(29, 158, 117, 0.1)',
                border: '1px solid rgba(29, 158, 117, 0.2)',
                marginBottom: '40px',
              }}
            >
              <div
                style={{
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  background: '#1D9E75',
                  boxShadow: '0 0 8px rgba(29, 158, 117, 0.6)',
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
                Efficiency Mode
              </span>
            </div>

            <h3 style={{ fontSize: '48px', fontWeight: 800, letterSpacing: '-0.04em', marginBottom: '24px' }}>
              LayerStream
            </h3>
            <p style={{ fontSize: '18px', fontWeight: 300, color: 'rgba(255,255,255,0.35)', lineHeight: 1.7, marginBottom: '40px', maxWidth: '380px' }}>
              Memory-efficient streaming. Model layers loaded dynamically from storage. Infinite capacity on any hardware.
            </p>

            {/* Features */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {FEATURES_LAYER.map((feat) => (
                <div key={feat} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{ width: '4px', height: '4px', borderRadius: '50%', background: '#1D9E75' }} />
                  <span
                    style={{
                      fontSize: '10px',
                      fontWeight: 800,
                      letterSpacing: '0.15em',
                      textTransform: 'uppercase' as const,
                      color: 'rgba(255,255,255,0.2)',
                    }}
                  >
                    {feat}
                  </span>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}