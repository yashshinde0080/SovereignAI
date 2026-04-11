'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const TOTAL_FRAMES = 240;
const LERP_FACTOR = 0.08;

/* ──────────────────────────────────────────────────────────
 * CONTENT SECTIONS — each pinned to a frame range
 * The scroll height is 1200vh total, so each "section"
 * occupies a scroll band mapped to a frame range.
 *
 * Structure:
 *   0–15%   → Hero / Intro (frames 1–36)
 *   15–30%  → Feature 1 — Sovereign Compute (frames 36–72)
 *   30–48%  → Feature 2 — Dual Execution (frames 72–115)
 *   48–65%  → Feature 3 — Architecture (frames 115–156)
 *   65–82%  → Feature 4 — Security (frames 156–197)
 *   82–100% → CTA / Finale (frames 197–240)
 * ────────────────────────────────────────────────────────── */

interface ContentSection {
  id: string;
  startProgress: number;
  endProgress: number;
  eyebrow: string;
  title: string;
  titleAccent?: string;
  description: string;
  features?: string[];
  badge?: { label: string; color: string };
  alignment: 'center' | 'left' | 'right';
}

const SECTIONS: ContentSection[] = [
  {
    id: 'hero',
    startProgress: 0.0,
    endProgress: 0.14,
    eyebrow: 'Sovereign Compute Infrastructure',
    title: 'SovereignAI',
    titleAccent: 'Edge',
    description: 'Where Intelligence Meets Motion',
    alignment: 'center',
  },
  {
    id: 'compute',
    startProgress: 0.16,
    endProgress: 0.29,
    eyebrow: 'Offline-First AI',
    title: 'No Cloud.',
    titleAccent: 'No Limits.',
    description:
      'Portable, self-contained AI infrastructure. Run LLMs on any hardware — laptops, edge devices, air-gapped servers. Zero dependency on cloud providers.',
    features: ['Run on any x86/ARM hardware', 'USB-bootable deployment', 'Zero internet required'],
    badge: { label: 'Core Technology', color: '#3C3489' },
    alignment: 'left',
  },
  {
    id: 'engines',
    startProgress: 0.31,
    endProgress: 0.47,
    eyebrow: 'Dual Execution',
    title: 'Two engines.',
    titleAccent: 'One system.',
    description:
      'FullRAM mode loads the entire model into memory for maximum throughput. LayerStream pages layers from storage for infinite capacity on minimal hardware.',
    features: ['FullRAM — instant token generation', 'LayerStream — SSD-based paging', 'Dynamic mode switching'],
    badge: { label: 'Performance', color: '#1D9E75' },
    alignment: 'right',
  },
  {
    id: 'architecture',
    startProgress: 0.49,
    endProgress: 0.64,
    eyebrow: 'System Architecture',
    title: 'Built for',
    titleAccent: 'constraint.',
    description:
      'Multi-threaded tensor processing, intelligent KV cache management, and zero-copy data pipelines. Memory is not a limitation — storage becomes compute.',
    features: ['Multi-threaded tensor cores', 'Dynamic KV cache', 'Zero-copy pipeline', 'Hardware-native execution'],
    badge: { label: 'Architecture', color: '#3C3489' },
    alignment: 'left',
  },
  {
    id: 'security',
    startProgress: 0.66,
    endProgress: 0.81,
    eyebrow: 'Security Verified',
    title: 'Nothing leaves',
    titleAccent: 'the machine.',
    description:
      'Air-gapped capable. Zero telemetry. No data ever leaves your hardware. Absolute compute sovereignty for classified and sensitive workloads.',
    features: ['Air-gapped operation', 'Zero telemetry', 'Complete data sovereignty'],
    badge: { label: 'Security', color: '#1D9E75' },
    alignment: 'right',
  },
  {
    id: 'cta',
    startProgress: 0.83,
    endProgress: 0.98,
    eyebrow: 'Available Now',
    title: 'Run AI',
    titleAccent: 'anywhere.',
    description: 'Sovereign compute. No compromises. Deploy on any hardware in minutes.',
    alignment: 'center',
  },
];

/**
 * ScrollSequence — Full-page cinematic scroll-driven frame animation
 *
 * The entire page is one giant scroll container (1200vh).
 * A sticky canvas renders frame images as background.
 * Content sections float on top, fading in/out at mapped scroll positions.
 */
export default function ScrollSequence() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [images, setImages] = useState<HTMLImageElement[]>([]);
  const [loadProgress, setLoadProgress] = useState(0);
  const [isLoaded, setIsLoaded] = useState(false);
  const [scrollProgress, setScrollProgress] = useState(0);

  // Refs for rAF loop
  const targetFrame = useRef(0);
  const currentFrame = useRef(0);
  const rafId = useRef(0);
  const lastDrawn = useRef(-1);

  // ===== PRELOAD ALL FRAMES =====
  useEffect(() => {
    let cancelled = false;
    const imgs: HTMLImageElement[] = new Array(TOTAL_FRAMES);
    let loaded = 0;

    const loadFrame = (index: number): Promise<void> => {
      return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => {
          if (!cancelled) {
            imgs[index] = img;
            loaded++;
            setLoadProgress((loaded / TOTAL_FRAMES) * 100);
          }
          resolve();
        };
        img.onerror = () => {
          loaded++;
          setLoadProgress((loaded / TOTAL_FRAMES) * 100);
          resolve();
        };
        img.src = `/frames/frame-${String(index + 1).padStart(3, '0')}.jpg`;
      });
    };

    const preloadAll = async () => {
      const BATCH = 8;
      for (let start = 0; start < TOTAL_FRAMES && !cancelled; start += BATCH) {
        const end = Math.min(start + BATCH, TOTAL_FRAMES);
        const batch = [];
        for (let i = start; i < end; i++) {
          batch.push(loadFrame(i));
        }
        await Promise.all(batch);
      }

      if (!cancelled) {
        const validImages = imgs.filter(Boolean);
        if (validImages.length > 0) {
          setImages(imgs);
        }
        setIsLoaded(true);
      }
    };

    preloadAll();
    return () => { cancelled = true; };
  }, []);

  // ===== DRAW FRAME TO CANVAS =====
  const drawFrame = useCallback(
    (frameIdx: number) => {
      const canvas = canvasRef.current;
      if (!canvas || !images || images.length === 0) return;

      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const idx = Math.max(0, Math.min(Math.round(frameIdx), TOTAL_FRAMES - 1));
      if (idx === lastDrawn.current) return;
      lastDrawn.current = idx;

      const img = images[idx];
      if (!img || !img.complete || img.naturalWidth === 0) return;

      const dpr = window.devicePixelRatio || 1;
      const w = window.innerWidth;
      const h = window.innerHeight;

      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        canvas.style.width = w + 'px';
        canvas.style.height = h + 'px';
      }

      // Cover-fit
      const imgR = img.naturalWidth / img.naturalHeight;
      const canR = w / h;
      let dw: number, dh: number, dx: number, dy: number;

      if (canR > imgR) {
        dw = w * dpr;
        dh = dw / imgR;
        dx = 0;
        dy = (h * dpr - dh) / 2;
      } else {
        dh = h * dpr;
        dw = dh * imgR;
        dx = (w * dpr - dw) / 2;
        dy = 0;
      }

      ctx.clearRect(0, 0, w * dpr, h * dpr);
      ctx.drawImage(img, dx, dy, dw, dh);
    },
    [images],
  );

  // ===== SCROLL → TARGET FRAME =====
  useEffect(() => {
    if (!isLoaded || !images || images.length === 0) return;

    const onScroll = () => {
      const el = containerRef.current;
      if (!el) return;

      const rect = el.getBoundingClientRect();
      const scrollable = rect.height - window.innerHeight;
      if (scrollable <= 0) return;

      const progress = Math.max(0, Math.min(1, -rect.top / scrollable));
      targetFrame.current = progress * (TOTAL_FRAMES - 1);
      setScrollProgress(progress);
    };

    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    return () => window.removeEventListener('scroll', onScroll);
  }, [isLoaded, images]);

  // ===== PERSISTENT rAF LOOP WITH LERP =====
  useEffect(() => {
    if (!isLoaded || !images || images.length === 0) return;

    drawFrame(0);

    const tick = () => {
      const diff = targetFrame.current - currentFrame.current;
      if (Math.abs(diff) > 0.05) {
        currentFrame.current += diff * LERP_FACTOR;
        drawFrame(currentFrame.current);
      }
      rafId.current = requestAnimationFrame(tick);
    };

    rafId.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId.current);
  }, [isLoaded, images, drawFrame]);

  // ===== RESIZE =====
  useEffect(() => {
    const onResize = () => {
      lastDrawn.current = -1;
      drawFrame(currentFrame.current);
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [drawFrame]);

  return (
    <div
      ref={containerRef}
      style={{ position: 'relative', width: '100%', height: '1200vh' }}
    >
      {/* ===== LOADING SCREEN ===== */}
      <AnimatePresence>
        {!isLoaded && (
          <motion.div
            key="loader"
            exit={{ opacity: 0, filter: 'blur(12px)' }}
            transition={{ duration: 1.4, ease: [0.22, 1, 0.36, 1] }}
            style={{
              position: 'fixed',
              inset: 0,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              background: '#050505',
              zIndex: 300,
            }}
          >
            {/* Loader background pulse */}
            <div
              style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                width: '600px',
                height: '400px',
                background:
                  'radial-gradient(ellipse, rgba(60,52,137,0.06) 0%, transparent 70%)',
                pointerEvents: 'none',
              }}
            />

            {/* Progress ring */}
            <div style={{ position: 'relative', marginBottom: '40px' }}>
              <svg width="100" height="100" viewBox="0 0 100 100">
                <circle
                  cx="50"
                  cy="50"
                  r="42"
                  fill="none"
                  stroke="rgba(255,255,255,0.03)"
                  strokeWidth="1.5"
                />
                <circle
                  cx="50"
                  cy="50"
                  r="42"
                  fill="none"
                  stroke="url(#loaderGrad)"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeDasharray={`${2 * Math.PI * 42}`}
                  strokeDashoffset={`${2 * Math.PI * 42 * (1 - loadProgress / 100)}`}
                  style={{
                    transform: 'rotate(-90deg)',
                    transformOrigin: '50% 50%',
                    transition: 'stroke-dashoffset 0.3s ease',
                  }}
                />
                <defs>
                  <linearGradient id="loaderGrad" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stopColor="#3C3489" />
                    <stop offset="100%" stopColor="#1D9E75" />
                  </linearGradient>
                </defs>
              </svg>
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <span
                  style={{
                    fontSize: '18px',
                    fontWeight: 700,
                    letterSpacing: '-0.02em',
                    color: 'rgba(255,255,255,0.15)',
                  }}
                >
                  {Math.round(loadProgress)}
                </span>
              </div>
            </div>

            <p
              style={{
                fontSize: '10px',
                fontWeight: 900,
                letterSpacing: '0.25em',
                textTransform: 'uppercase' as const,
                color: 'rgba(255,255,255,0.2)',
              }}
            >
              Loading Sovereign Core
            </p>

            {/* Thin progress bar */}
            <div
              style={{
                width: '160px',
                height: '1px',
                background: 'rgba(255,255,255,0.04)',
                borderRadius: '2px',
                overflow: 'hidden',
                marginTop: '20px',
              }}
            >
              <motion.div
                style={{
                  height: '100%',
                  background: 'linear-gradient(90deg, #3C3489, #1D9E75)',
                  borderRadius: '2px',
                }}
                initial={{ width: 0 }}
                animate={{ width: `${loadProgress}%` }}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ===== STICKY CANVAS BACKGROUND ===== */}
      <div
        style={{
          position: 'sticky',
          top: 0,
          left: 0,
          width: '100%',
          height: '100vh',
          overflow: 'clip',
          background: '#050505',
          zIndex: 1,
        }}
      >
        <canvas
          ref={canvasRef}
          style={{ display: 'block', width: '100%', height: '100%' }}
        />

        {/* Cinematic vignette overlay — darkens for text readability */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            pointerEvents: 'none',
            background: `
              linear-gradient(to bottom, rgba(5,5,5,0.7) 0%, rgba(5,5,5,0.25) 18%, rgba(5,5,5,0.2) 50%, rgba(5,5,5,0.25) 82%, rgba(5,5,5,0.7) 100%),
              linear-gradient(to right, rgba(5,5,5,0.5) 0%, transparent 25%, transparent 75%, rgba(5,5,5,0.5) 100%)
            `,
          }}
        />
        {/* Extra dark scrim — adjusts dynamically based on scroll */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            pointerEvents: 'none',
            background: 'rgba(0,0,0,0.35)',
          }}
        />

        {/* Content overlay on top of canvas */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            zIndex: 10,
            pointerEvents: 'none',
          }}
        >
          {SECTIONS.map((section) => (
            <SectionOverlay
              key={section.id}
              section={section}
              scrollProgress={scrollProgress}
            />
          ))}
        </div>

        {/* Scroll progress bar */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: `${scrollProgress * 100}%`,
            height: '2px',
            background: 'linear-gradient(90deg, #3C3489, #1D9E75)',
            zIndex: 50,
            transition: 'width 0.1s linear',
          }}
        />

        {/* Frame counter */}
        <div
          style={{
            position: 'absolute',
            bottom: '24px',
            right: '24px',
            zIndex: 40,
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <span
            style={{
              fontSize: '9px',
              fontWeight: 900,
              letterSpacing: '0.2em',
              textTransform: 'uppercase' as const,
              color: 'rgba(255,255,255,0.08)',
            }}
          >
            Frame
          </span>
          <span
            style={{
              fontSize: '11px',
              fontWeight: 700,
              fontVariantNumeric: 'tabular-nums',
              color: 'rgba(255,255,255,0.12)',
              letterSpacing: '-0.02em',
            }}
          >
            {String(Math.round(scrollProgress * (TOTAL_FRAMES - 1)) + 1).padStart(3, '0')} / {TOTAL_FRAMES}
          </span>
        </div>

        {/* Scroll indicator — only at beginning */}
        {scrollProgress < 0.03 && isLoaded && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.5, duration: 1 }}
            style={{
              position: 'absolute',
              bottom: '48px',
              left: '50%',
              transform: 'translateX(-50%)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '12px',
              zIndex: 30,
            }}
          >
            <span
              style={{
                fontSize: '9px',
                fontWeight: 900,
                letterSpacing: '0.25em',
                textTransform: 'uppercase' as const,
                color: 'rgba(255,255,255,0.15)',
              }}
            >
              Scroll to explore
            </span>
            <motion.div
              animate={{ y: [0, 8, 0] }}
              transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
              style={{
                width: '1px',
                height: '40px',
                background:
                  'linear-gradient(to bottom, rgba(255,255,255,0.2), transparent)',
              }}
            />
          </motion.div>
        )}
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
 * SectionOverlay — A content panel that fades in/out based
 * on the current scroll progress matching its frame range
 * ──────────────────────────────────────────────────────────── */
function SectionOverlay({
  section,
  scrollProgress,
}: {
  section: ContentSection;
  scrollProgress: number;
}) {
  const { startProgress, endProgress, alignment } = section;
  const midpoint = (startProgress + endProgress) / 2;
  const range = endProgress - startProgress;
  const fadeInEnd = startProgress + range * 0.2;
  const fadeOutStart = endProgress - range * 0.2;

  // Compute opacity: fade in → hold → fade out
  let opacity = 0;
  if (scrollProgress >= startProgress && scrollProgress <= endProgress) {
    if (scrollProgress < fadeInEnd) {
      opacity = startProgress === 0 ? 1 : (scrollProgress - startProgress) / (fadeInEnd - startProgress);
    } else if (scrollProgress > fadeOutStart) {
      opacity = endProgress >= 0.95 ? 1 : (endProgress - scrollProgress) / (endProgress - fadeOutStart);
    } else {
      opacity = 1;
    }
  }

  // Parallax Y offset based on progress within section
  const sectionProgress =
    (scrollProgress - startProgress) / (endProgress - startProgress);
  const translateY = Math.max(-30, Math.min(30, (0.5 - sectionProgress) * 60));

  if (opacity < 0.01) return null;

  // Position based on alignment
  const positionStyles: React.CSSProperties =
    alignment === 'center'
      ? {
          left: '50%',
          top: '50%',
          transform: `translate(-50%, -50%) translateY(${translateY}px)`,
          textAlign: 'center',
          maxWidth: '800px',
          width: '100%',
          padding: '0 32px',
        }
      : alignment === 'left'
      ? {
          left: '6vw',
          top: '50%',
          transform: `translateY(-50%) translateY(${translateY}px)`,
          textAlign: 'left',
          maxWidth: '560px',
          width: '100%',
        }
      : {
          right: '6vw',
          top: '50%',
          transform: `translateY(-50%) translateY(${translateY}px)`,
          textAlign: 'right',
          maxWidth: '560px',
          width: '100%',
        };

  const isHero = section.id === 'hero';
  const isCTA = section.id === 'cta';

  return (
    <div
      style={{
        position: 'absolute',
        opacity,
        transition: 'opacity 0.15s ease',
        pointerEvents: opacity > 0.5 ? 'auto' : 'none',
        zIndex: 20,
        ...positionStyles,
      }}
    >
      {/* Badge */}
      {section.badge && (
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 16px',
            borderRadius: '9999px',
            background: `${section.badge.color}15`,
            border: `1px solid ${section.badge.color}33`,
            marginBottom: '32px',
          }}
        >
          <div
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              background: section.badge.color,
              boxShadow: `0 0 8px ${section.badge.color}80`,
            }}
          />
          <span
            style={{
              fontSize: '9px',
              fontWeight: 900,
              letterSpacing: '0.15em',
              textTransform: 'uppercase' as const,
              color: section.badge.color,
            }}
          >
            {section.badge.label}
          </span>
        </div>
      )}

      {/* Eyebrow */}
      <p
        style={{
          fontSize: isHero ? '11px' : '10px',
          fontWeight: 900,
          letterSpacing: '0.3em',
          textTransform: 'uppercase' as const,
          color: '#1D9E75',
          marginBottom: isHero ? '36px' : '20px',
        }}
      >
        {section.eyebrow}
      </p>

      {/* Title */}
      <h2
        style={{
          fontSize: isHero
            ? 'clamp(3.5rem, 11vw, 9rem)'
            : isCTA
            ? 'clamp(4rem, 10vw, 9rem)'
            : 'clamp(2.5rem, 6vw, 6rem)',
          fontWeight: 800,
          letterSpacing: isHero ? '-0.06em' : '-0.05em',
          lineHeight: isHero ? 0.88 : 1,
          marginBottom: section.titleAccent ? '4px' : '32px',
          color: '#fff',
          textShadow: '0 2px 30px rgba(0,0,0,0.9), 0 0 60px rgba(0,0,0,0.5)',
        }}
      >
        {section.title}
      </h2>

      {/* Title accent */}
      {section.titleAccent && (
        <h2
          style={{
            fontSize: isHero
              ? 'clamp(3.5rem, 11vw, 9rem)'
              : isCTA
              ? 'clamp(4rem, 10vw, 9rem)'
              : 'clamp(2.5rem, 6vw, 6rem)',
            fontWeight: 200,
            fontStyle: 'italic',
            letterSpacing: isHero ? '-0.06em' : '-0.05em',
            lineHeight: isHero ? 0.88 : 1,
            color: 'rgba(255, 255, 255, 0.2)',
            marginBottom: isHero ? '40px' : '32px',
            textShadow: '0 2px 20px rgba(0,0,0,0.7)',
          }}
        >
          {section.titleAccent}
        </h2>
      )}

      {/* Description */}
      <p
        style={{
          fontSize: isHero
            ? 'clamp(17px, 2.2vw, 24px)'
            : 'clamp(15px, 1.8vw, 20px)',
          fontWeight: 300,
          color: 'rgba(255, 255, 255, 0.5)',
          letterSpacing: '-0.01em',
          lineHeight: 1.7,
          marginBottom: section.features ? '40px' : isCTA ? '48px' : '0',
          maxWidth: alignment === 'center' ? '500px' : '100%',
          margin:
            alignment === 'center'
              ? `0 auto ${section.features ? '40px' : isCTA ? '48px' : '0'}`
              : undefined,
          textShadow: '0 2px 16px rgba(0,0,0,0.8)',
        }}
      >
        {section.description}
      </p>

      {/* Features list */}
      {section.features && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '14px',
            alignItems:
              alignment === 'center'
                ? 'center'
                : alignment === 'right'
                ? 'flex-end'
                : 'flex-start',
          }}
        >
          {section.features.map((feat, i) => (
            <div
              key={feat}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                opacity: Math.min(
                  1,
                  Math.max(0, (opacity - 0.3 - i * 0.1) / 0.3),
                ),
              }}
            >
              <div
                style={{
                  width: '4px',
                  height: '4px',
                  borderRadius: '50%',
                  background: section.badge?.color || '#1D9E75',
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 800,
                  letterSpacing: '0.12em',
                  textTransform: 'uppercase' as const,
                  color: 'rgba(255,255,255,0.25)',
                }}
              >
                {feat}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Hero buttons */}
      {isHero && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '20px',
            marginTop: '8px',
          }}
        >
          <button
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
              pointerEvents: 'auto',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.boxShadow = '0 0 40px rgba(60, 52, 137, 0.4)';
              e.currentTarget.style.transform = 'scale(1.06)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.boxShadow = 'none';
              e.currentTarget.style.transform = 'scale(1)';
            }}
          >
            Explore Now
          </button>
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
              pointerEvents: 'auto',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#fff')}
            onMouseLeave={(e) =>
              (e.currentTarget.style.color = 'rgba(255,255,255,0.3)')
            }
          >
            Technical Specs →
          </button>
        </div>
      )}

      {/* CTA button */}
      {isCTA && (
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
          }}
        >
          <button
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
              boxShadow:
                '0 0 60px rgba(255,255,255,0.1), 0 25px 50px rgba(0,0,0,0.5)',
              transition: 'all 0.5s ease',
              pointerEvents: 'auto',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#3C3489';
              e.currentTarget.style.color = '#fff';
              e.currentTarget.style.transform = 'scale(1.05)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#fff';
              e.currentTarget.style.color = '#000';
              e.currentTarget.style.transform = 'scale(1)';
            }}
          >
            Deploy SovereignAI Edge
          </button>
        </div>
      )}
    </div>
  );
}