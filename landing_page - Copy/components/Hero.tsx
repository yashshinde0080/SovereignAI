'use client';

import { motion } from 'framer-motion';

/**
 * Hero Section — Cinematic intro with staggered reveal animations
 * 
 * Features:
 * - Staggered fade-in + slide-up for all text elements
 * - Volumetric indigo glow background  
 * - Glassmorphic button with hover glow
 * - Parallax-ready: slower than scroll background
 */

// Stagger container
const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.15, delayChildren: 0.3 } },
};

// Individual element slide-up reveal
const fadeUp = {
  hidden: { opacity: 0, y: 40, filter: 'blur(4px)' },
  show: { 
    opacity: 1, y: 0, filter: 'blur(0px)',
    transition: { duration: 1.2, ease: [0.22, 1, 0.36, 1] }
  },
};

export default function Hero() {
  return (
    <section
      style={{
        position: 'relative',
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#050505',
        overflow: 'hidden',
      }}
    >
      {/* Volumetric Core Glow */}
      <div
        style={{
          position: 'absolute',
          top: '35%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: '1000px',
          height: '600px',
          background: 'radial-gradient(ellipse, rgba(60, 52, 137, 0.12) 0%, rgba(29, 158, 117, 0.04) 40%, transparent 70%)',
          filter: 'blur(60px)',
          pointerEvents: 'none',
        }}
      />

      {/* Hero Content — Staggered Reveal */}
      <motion.div
        variants={stagger}
        initial="hidden"
        animate="show"
        style={{
          position: 'relative',
          zIndex: 10,
          textAlign: 'center',
          padding: '0 32px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
        }}
      >
        {/* Eyebrow */}
        <motion.p
          variants={fadeUp}
          style={{
            fontSize: '11px',
            fontWeight: 900,
            letterSpacing: '0.3em',
            textTransform: 'uppercase' as const,
            color: '#1D9E75',
            marginBottom: '36px',
          }}
        >
          Sovereign Compute Infrastructure
        </motion.p>

        {/* Main Title — Split for dramatic reveal */}
        <motion.h1
          variants={fadeUp}
          className="text-gradient"
          style={{
            fontSize: 'clamp(3.5rem, 11vw, 9rem)',
            fontWeight: 800,
            letterSpacing: '-0.06em',
            lineHeight: 0.88,
            marginBottom: '4px',
          }}
        >
          SovereignAI
        </motion.h1>

        <motion.h1
          variants={fadeUp}
          style={{
            fontSize: 'clamp(3.5rem, 11vw, 9rem)',
            fontWeight: 200,
            fontStyle: 'italic',
            letterSpacing: '-0.06em',
            lineHeight: 0.88,
            color: 'rgba(255, 255, 255, 0.07)',
            marginBottom: '40px',
          }}
        >
          Edge
        </motion.h1>

        {/* Tagline */}
        <motion.p
          variants={fadeUp}
          style={{
            fontSize: 'clamp(17px, 2.2vw, 24px)',
            fontWeight: 300,
            color: 'rgba(255, 255, 255, 0.32)',
            letterSpacing: '-0.01em',
            marginBottom: '48px',
            maxWidth: '500px',
          }}
        >
          Where Intelligence Meets Motion
        </motion.p>

        {/* Buttons */}
        <motion.div
          variants={fadeUp}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '20px',
          }}
        >
          {/* Primary CTA — Glassmorphism */}
          <motion.button
            whileHover={{ scale: 1.06, boxShadow: '0 0 40px rgba(60, 52, 137, 0.4)' }}
            whileTap={{ scale: 0.97 }}
            style={{
              padding: '16px 40px',
              background: 'rgba(60, 52, 137, 0.15)',
              backdropFilter: 'blur(20px)',
              WebkitBackdropFilter: 'blur(20px)',
              border: '1px solid rgba(60, 52, 137, 0.3)',
              borderRadius: '9999px',
              color: '#fff',
              fontSize: '11px',
              fontWeight: 900,
              textTransform: 'uppercase' as const,
              letterSpacing: '0.15em',
              cursor: 'pointer',
              transition: 'all 0.5s cubic-bezier(0.22, 1, 0.36, 1)',
            }}
          >
            Explore Now
          </motion.button>

          {/* Secondary CTA */}
          <button
            style={{
              padding: '16px 24px',
              background: 'transparent',
              border: 'none',
              color: 'rgba(255, 255, 255, 0.3)',
              fontSize: '11px',
              fontWeight: 900,
              textTransform: 'uppercase' as const,
              letterSpacing: '0.15em',
              cursor: 'pointer',
              transition: 'color 0.4s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#fff')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.3)')}
          >
            Technical Specs →
          </button>
        </motion.div>
      </motion.div>

      {/* Scroll Indicator */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 2.2, duration: 1 }}
        style={{
          position: 'absolute',
          bottom: '40px',
          left: '50%',
          transform: 'translateX(-50%)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '10px',
        }}
      >
        <span
          style={{
            fontSize: '9px',
            fontWeight: 900,
            letterSpacing: '0.2em',
            textTransform: 'uppercase' as const,
            color: 'rgba(255, 255, 255, 0.12)',
          }}
        >
          Scroll to discover
        </span>
        <motion.div
          animate={{ y: [0, 6, 0] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          style={{
            width: '1px',
            height: '36px',
            background: 'linear-gradient(to bottom, rgba(255,255,255,0.15), transparent)',
          }}
        />
      </motion.div>
    </section>
  );
}