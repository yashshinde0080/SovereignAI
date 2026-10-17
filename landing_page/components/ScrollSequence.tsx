'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const TOTAL_FRAMES = 240;
const CRITICAL_FRAMES = 24;
const LERP_FACTOR = 0.08;
const REPO_URL = 'https://github.com/yashshinde0080/SovereignAI';

/* ──────────────────────────────────────────────────────────
 * CONTENT SECTIONS — each pinned to a frame range.
 * Scroll height is 1200vh; each section occupies a scroll
 * band mapped to a frame range.
 * ────────────────────────────────────────────────────────── */

interface ContentSection {
  id: string;
  anchorId: string;
  startProgress: number;
  endProgress: number;
  title: string;
  titleAccent?: string;
  description: string;
  features?: string[];
  badge?: { label: string; color: string };
  ctaNote?: string;
  alignment: 'center' | 'left' | 'right';
}

const SECTIONS: ContentSection[] = [
  {
    id: 'hero',
    anchorId: 'overview',
    startProgress: 0.0,
    endProgress: 0.14,
    title: 'SovereignAI',
    titleAccent: 'Edge',
    description: 'Where Intelligence Meets Motion',
    alignment: 'center',
  },
  {
    id: 'compute',
    anchorId: 'compute',
    startProgress: 0.16,
    endProgress: 0.29,
    title: 'No Cloud.',
    titleAccent: 'No Limits.',
    description:
      'Portable, self-contained AI infrastructure. Run LLMs on any hardware — laptops, edge devices, air-gapped servers. Zero dependency on cloud providers.',
    features: ['Run on any x86/ARM hardware', 'USB-bootable deployment', 'Zero internet required'],
    badge: { label: 'Core Technology', color: '#8B84D8' },
    alignment: 'left',
  },
  {
    id: 'engines',
    anchorId: 'engines',
    startProgress: 0.31,
    endProgress: 0.47,
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
    anchorId: 'architecture',
    startProgress: 0.49,
    endProgress: 0.64,
    title: 'Built for',
    titleAccent: 'constraint.',
    description:
      'Multi-threaded tensor processing, intelligent KV cache management, and zero-copy data pipelines. Memory is not a limitation — storage becomes compute.',
    features: ['Multi-threaded tensor cores', 'Dynamic KV cache', 'Zero-copy pipeline', 'Hardware-native execution'],
    badge: { label: 'Architecture', color: '#8B84D8' },
    alignment: 'left',
  },
  {
    id: 'security',
    anchorId: 'security',
    startProgress: 0.66,
    endProgress: 0.81,
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
    anchorId: 'deploy',
    startProgress: 0.83,
    endProgress: 0.98,
    title: 'Run AI',
    titleAccent: 'anywhere.',
    description: 'Sovereign compute. No compromises. Deploy on any hardware in minutes.',
    ctaNote: 'Available now · Open repository',
    alignment: 'center',
  },
];

/**
 * ScrollSequence — full-page cinematic scroll-driven frame animation.
 * One 1200vh scroll container; a sticky canvas renders frame images;
 * content sections float on top, fading in/out at mapped scroll positions.
 */
export default function ScrollSequence() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const framesRef = useRef<(HTMLImageElement | null)[]>([]);
  const [loadPercent, setLoadPercent] = useState(0);
  const [ready, setReady] = useState(false);
  const [scrollProgress, setScrollProgress] = useState(0);

  const targetFrame = useRef(0);
  const currentFrame = useRef(0);
  const rafId = useRef(0);
  const lastDrawn = useRef(-1);
  const dprRef = useRef(1);
  const reducedRef = useRef(false);
  const scrollTicking = useRef(false);

  // ===== STAGED FRAME LOADING =====
  // Hero-critical frames first (unlocks the experience), the rest warm in
  // the background. Progress state updates only on whole-percent changes.
  useEffect(() => {
    let cancelled = false;
    let loaded = 0;
    let lastPct = -1;

    reducedRef.current = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    dprRef.current = window.devicePixelRatio || 1;

    const loadFrame = (index: number): Promise<void> =>
      new Promise((resolve) => {
        const img = new Image();
        img.onload = () => {
          if (!cancelled) {
            framesRef.current[index] = img;
            loaded++;
            const pct = Math.floor((loaded / TOTAL_FRAMES) * 100);
            if (pct !== lastPct) {
              lastPct = pct;
              setLoadPercent(pct);
            }
          }
          resolve();
        };
        img.onerror = () => {
          loaded++;
          resolve();
        };
        img.src = `/frames/frame-${String(index + 1).padStart(3, '0')}.jpg`;
      });

    const loadRange = async (from: number, to: number) => {
      const BATCH = 8;
      for (let start = from; start < to && !cancelled; start += BATCH) {
        const end = Math.min(start + BATCH, to);
        await Promise.all(Array.from({ length: end - start }, (_, k) => loadFrame(start + k)));
      }
    };

    (async () => {
      await loadRange(0, CRITICAL_FRAMES);
      if (cancelled) return;
      setReady(true);
      loadRange(CRITICAL_FRAMES, TOTAL_FRAMES);
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  // ===== DRAW FRAME TO CANVAS =====
  const drawFrame = useCallback((frameIdx: number) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const idx = Math.max(0, Math.min(Math.round(frameIdx), TOTAL_FRAMES - 1));
    if (idx === lastDrawn.current) return;

    const img = framesRef.current[idx];
    // Frame still warming up — keep the last drawn image, retry next tick.
    if (!img || !img.complete || img.naturalWidth === 0) return;
    lastDrawn.current = idx;

    const dpr = dprRef.current;
    const w = window.innerWidth;
    const h = window.innerHeight;

    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
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
  }, []);

  // ===== SCROLL → TARGET FRAME (rAF-throttled) =====
  useEffect(() => {
    if (!ready) return;

    const read = () => {
      scrollTicking.current = false;
      const el = containerRef.current;
      if (!el) return;

      const rect = el.getBoundingClientRect();
      const scrollable = rect.height - window.innerHeight;
      if (scrollable <= 0) return;

      const progress = Math.max(0, Math.min(1, -rect.top / scrollable));
      targetFrame.current = progress * (TOTAL_FRAMES - 1);
      setScrollProgress((prev) => {
        const next = Math.round(progress * 1000) / 1000;
        return next === prev ? prev : next;
      });
    };

    const onScroll = () => {
      if (!scrollTicking.current) {
        scrollTicking.current = true;
        requestAnimationFrame(read);
      }
    };

    window.addEventListener('scroll', onScroll, { passive: true });
    read();

    return () => window.removeEventListener('scroll', onScroll);
  }, [ready]);

  // ===== PERSISTENT rAF LOOP WITH LERP =====
  useEffect(() => {
    if (!ready) return;

    drawFrame(0);

    const tick = () => {
      const diff = targetFrame.current - currentFrame.current;
      if (Math.abs(diff) > 0.05) {
        currentFrame.current = reducedRef.current
          ? targetFrame.current
          : currentFrame.current + diff * LERP_FACTOR;
        drawFrame(currentFrame.current);
      }
      rafId.current = requestAnimationFrame(tick);
    };

    rafId.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId.current);
  }, [ready, drawFrame]);

  // ===== RESIZE =====
  useEffect(() => {
    const onResize = () => {
      dprRef.current = window.devicePixelRatio || 1;
      lastDrawn.current = -1;
      drawFrame(currentFrame.current);
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [drawFrame]);

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%', height: '1200vh' }}>
      {/* Anchor targets so navbar / hero links land on the right scroll band */}
      {SECTIONS.map((s) => {
        const p = s.startProgress + (s.endProgress - s.startProgress) * 0.3;
        return (
          <span
            key={s.anchorId}
            id={s.anchorId}
            aria-hidden="true"
            style={{
              position: 'absolute',
              left: 0,
              width: 0,
              height: 0,
              top: `calc(${(p * 100).toFixed(2)}% - ${(p * 100).toFixed(2)}vh)`,
            }}
          />
        );
      })}

      {/* ===== LOADING SCREEN (critical frames only) ===== */}
      <AnimatePresence>
        {!ready && (
          <motion.div
            key="loader"
            exit={{ opacity: 0, filter: 'blur(12px)' }}
            transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
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
            <div
              style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                width: '600px',
                height: '400px',
                background:
                  'radial-gradient(ellipse, rgba(60,52,137,0.08) 0%, transparent 70%)',
                pointerEvents: 'none',
              }}
            />

            <div
              role="progressbar"
              aria-valuenow={loadPercent}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Loading cinematic sequence"
              style={{ position: 'relative', marginBottom: '40px' }}
            >
              <svg width="100" height="100" viewBox="0 0 100 100">
                <circle
                  cx="50"
                  cy="50"
                  r="42"
                  fill="none"
                  stroke="rgba(255,255,255,0.06)"
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
                  strokeDashoffset={`${2 * Math.PI * 42 * (1 - loadPercent / 100)}`}
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
                    fontSize: '16px',
                    fontWeight: 700,
                    letterSpacing: '-0.02em',
                    fontVariantNumeric: 'tabular-nums',
                    color: 'rgba(255,255,255,0.55)',
                  }}
                >
                  {loadPercent}%
                </span>
              </div>
            </div>

            <p
              style={{
                fontSize: '10px',
                fontWeight: 800,
                letterSpacing: '0.25em',
                textTransform: 'uppercase',
                color: 'rgba(255,255,255,0.45)',
              }}
            >
              Loading Sovereign Core
            </p>

            <div
              style={{
                width: '160px',
                height: '1px',
                background: 'rgba(255,255,255,0.06)',
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
                animate={{ width: `${loadPercent}%` }}
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
          role="img"
          aria-label="Cinematic animation of SovereignAI Edge running locally"
          style={{ display: 'block', width: '100%', height: '100%' }}
        />

        {/* Cinematic vignette — darkens edges for text readability */}
        <div
          aria-hidden="true"
          style={{
            position: 'absolute',
            inset: 0,
            pointerEvents: 'none',
            background: `
              linear-gradient(to bottom, rgba(5,5,5,0.72) 0%, rgba(5,5,5,0.32) 18%, rgba(5,5,5,0.42) 50%, rgba(5,5,5,0.32) 82%, rgba(5,5,5,0.72) 100%),
              linear-gradient(to right, rgba(5,5,5,0.5) 0%, transparent 25%, transparent 75%, rgba(5,5,5,0.5) 100%)
            `,
          }}
        />

        {/* Content overlay on top of canvas */}
        <div style={{ position: 'absolute', inset: 0, zIndex: 10, pointerEvents: 'none' }}>
          {SECTIONS.map((section) => (
            <SectionOverlay
              key={section.id}
              section={section}
              scrollProgress={scrollProgress}
              reduced={reducedRef.current}
            />
          ))}
        </div>

        {/* Scroll progress rail */}
        <div
          aria-hidden="true"
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

        {/* Scroll hint — only near the top */}
        {scrollProgress < 0.03 && ready && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.8, duration: 0.8 }}
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
            <span className="seq-hint-label">Scroll to explore</span>
            <motion.div
              animate={{ y: [0, 8, 0] }}
              transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
              style={{
                width: '1px',
                height: '40px',
                background: 'linear-gradient(to bottom, rgba(255,255,255,0.35), transparent)',
              }}
            />
          </motion.div>
        )}
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
 * SectionOverlay — content panel that fades in/out as the
 * scroll progress crosses its frame range
 * ──────────────────────────────────────────────────────────── */
function SectionOverlay({
  section,
  scrollProgress,
  reduced,
}: {
  section: ContentSection;
  scrollProgress: number;
  reduced: boolean;
}) {
  const { startProgress, endProgress, alignment } = section;
  const range = endProgress - startProgress;
  const fadeInEnd = startProgress + range * 0.2;
  const fadeOutStart = endProgress - range * 0.2;

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

  const sectionProgress = (scrollProgress - startProgress) / range;
  const translateY = reduced
    ? 0
    : Math.max(-30, Math.min(30, (0.5 - sectionProgress) * 60));

  if (opacity < 0.01) return null;

  const isHero = section.id === 'hero';
  const isCTA = section.id === 'cta';
  const Heading = isHero ? 'h1' : 'h2';
  const accentColor = section.badge?.color ?? '#1D9E75';

  return (
    <div
      className={`seq-panel seq-panel--${section.id}`}
      data-align={alignment}
      style={{
        opacity,
        pointerEvents: opacity > 0.5 ? 'auto' : 'none',
        ['--py' as string]: `${translateY}px`,
      } as React.CSSProperties}
    >
      {section.badge && (
        <div
          className="seq-badge"
          style={{
            background: `${section.badge.color}1f`,
            border: `1px solid ${section.badge.color}59`,
          }}
        >
          <span
            className="seq-badge-dot"
            style={{
              background: section.badge.color,
              boxShadow: `0 0 8px ${section.badge.color}cc`,
            }}
          />
          <span className="seq-badge-label" style={{ color: section.badge.color }}>
            {section.badge.label}
          </span>
        </div>
      )}

      <Heading className="seq-title">
        {section.title}
        {section.titleAccent && (
          <span className="seq-title-accent">{section.titleAccent}</span>
        )}
      </Heading>

      <p className="seq-desc">{section.description}</p>

      {section.features && (
        <ul className="seq-features" style={{ ['--seq-accent' as string]: accentColor } as React.CSSProperties}>
          {section.features.map((feat, i) => (
            <li
              key={feat}
              className="seq-feature"
              style={{
                opacity: Math.min(1, Math.max(0, (opacity - 0.3 - i * 0.1) / 0.3)),
              }}
            >
              <span className="seq-feature-dot" />
              <span className="seq-feature-label">{feat}</span>
            </li>
          ))}
        </ul>
      )}

      {isHero && (
        <div className="seq-actions">
          <a href="#compute" className="seq-btn">
            Explore Now
          </a>
          <a href="#architecture" className="seq-btn seq-btn--ghost">
            Technical Specs →
          </a>
        </div>
      )}

      {isCTA && (
        <div className="seq-actions" style={{ marginTop: 0 }}>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="seq-btn seq-btn--solid"
          >
            Deploy SovereignAI Edge
          </a>
        </div>
      )}
      {section.ctaNote && <p className="seq-cta-note">{section.ctaNote}</p>}
    </div>
  );
}
