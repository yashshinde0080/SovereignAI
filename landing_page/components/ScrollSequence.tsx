'use client';

import { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const TOTAL_FRAMES = 240;
const LERP_FACTOR = 0.07;

/**
 * ScrollSequence — Cinematic scroll-driven frame animation
 * 
 * Architecture:
 * 1. Preload all 240 frames into an Image[] array (batched, no timeout)
 * 2. Map scroll position → target frame index
 * 3. Persistent rAF loop lerps current frame toward target (smooth easing)
 * 4. Canvas renders with cover-fit aspect ratio
 */
export default function ScrollSequence() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [images, setImages] = useState<HTMLImageElement[]>([]);
  const [loadProgress, setLoadProgress] = useState(0);
  const [isLoaded, setIsLoaded] = useState(false);
  const [narrativeProgress, setNarrativeProgress] = useState(0);

  // Refs for rAF loop (no re-renders needed)
  const targetFrame = useRef(0);
  const currentFrame = useRef(0);
  const rafId = useRef(0);
  const lastDrawn = useRef(-1);

  // ===== STEP 1: PRELOAD ALL FRAMES =====
  useEffect(() => {
    let cancelled = false;
    const imgs: HTMLImageElement[] = new Array(TOTAL_FRAMES);
    let loaded = 0;

    // Simple sequential preloader — reliable, no connection flooding
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
        // Files: "frame-001.jpg" to "frame-240.jpg" in public/frames/
        img.src = `/frames/frame-${String(index + 1).padStart(3, '0')}.jpg`;
      });
    };

    const preloadAll = async () => {
      // Load in batches of 6 to stay within browser connection limits
      const BATCH = 6;
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
          setImages(validImages);
        }
        setIsLoaded(true);
      }
    };

    preloadAll();

    return () => { cancelled = true; };
  }, []);

  // ===== STEP 2: DRAW FRAME TO CANVAS (cover-fit) =====
  const drawFrame = useCallback((frameIdx: number) => {
    const canvas = canvasRef.current;
    if (!canvas || images.length === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const idx = Math.max(0, Math.min(Math.round(frameIdx), images.length - 1));
    if (idx === lastDrawn.current) return; // skip duplicate draws
    lastDrawn.current = idx;

    const img = images[idx];
    if (!img || !img.complete || img.naturalWidth === 0) return;

    const dpr = window.devicePixelRatio || 1;
    const w = window.innerWidth;
    const h = window.innerHeight;

    // Resize canvas buffer only when viewport changes
    if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = w + 'px';
      canvas.style.height = h + 'px';
    }

    // Cover-fit logic
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
  }, [images]);

  // ===== STEP 3: SCROLL → TARGET FRAME =====
  useEffect(() => {
    if (!isLoaded || images.length === 0) return;

    const onScroll = () => {
      const el = containerRef.current;
      if (!el) return;

      const rect = el.getBoundingClientRect();
      const scrollable = rect.height - window.innerHeight;
      if (scrollable <= 0) return;

      const progress = Math.max(0, Math.min(1, -rect.top / scrollable));
      targetFrame.current = progress * (images.length - 1);
      setNarrativeProgress(progress);
    };

    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    return () => window.removeEventListener('scroll', onScroll);
  }, [isLoaded, images]);

  // ===== STEP 4: PERSISTENT rAF LOOP WITH LERP =====
  useEffect(() => {
    if (!isLoaded || images.length === 0) return;

    drawFrame(0); // Draw first frame immediately

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

  // ===== STEP 5: RESIZE HANDLER =====
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
      id="overview"
      style={{ position: 'relative', width: '100%', height: '500vh' }}
    >
      {/* ===== LOADING SCREEN ===== */}
      <AnimatePresence>
        {!isLoaded && (
          <motion.div
            key="loader"
            exit={{ opacity: 0, filter: 'blur(8px)' }}
            transition={{ duration: 1.2, ease: [0.22, 1, 0.36, 1] }}
            style={{
              position: 'fixed',
              inset: 0,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              background: '#050505',
              zIndex: 200,
            }}
          >
            {/* Thin progress bar */}
            <div style={{
              width: '200px', height: '2px', background: 'rgba(255,255,255,0.04)',
              borderRadius: '2px', overflow: 'hidden', marginBottom: '28px',
            }}>
              <motion.div
                style={{ height: '100%', background: 'linear-gradient(90deg, #3C3489, #1D9E75)', borderRadius: '2px' }}
                initial={{ width: 0 }}
                animate={{ width: `${loadProgress}%` }}
              />
            </div>
            <p style={{
              fontSize: '10px', fontWeight: 800, letterSpacing: '0.2em',
              textTransform: 'uppercase' as const, color: 'rgba(255,255,255,0.25)',
            }}>
              Loading Sovereign Core
            </p>
            <p style={{
              fontSize: '32px', fontWeight: 800, letterSpacing: '-0.04em',
              color: 'rgba(255,255,255,0.06)', marginTop: '8px',
            }}>
              {Math.round(loadProgress)}%
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ===== STICKY CANVAS ===== */}
      <div style={{
        position: 'sticky', top: 0, left: 0,
        width: '100%', height: '100vh', overflow: 'hidden', background: '#050505',
      }}>
        <canvas ref={canvasRef} style={{ display: 'block', width: '100%', height: '100%' }} />

        {/* Cinematic vignette */}
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          background: 'linear-gradient(to bottom, #050505 0%, transparent 10%, transparent 90%, #050505 100%)',
          opacity: 0.5,
        }} />

        {/* Ambient glow */}
        <div style={{
          position: 'absolute', top: '50%', left: '50%',
          transform: 'translate(-50%, -50%)', width: '800px', height: '500px',
          background: 'radial-gradient(ellipse, rgba(60,52,137,0.03) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />
      </div>

      {/* ===== SCROLL NARRATIVE ===== */}
      <NarrativeOverlay progress={narrativeProgress} />
    </div>
  );
}

/* ===== Phase Narrative ===== */
function NarrativeOverlay({ progress }: { progress: number }) {
  const data = useMemo(() => {
    if (progress < 0.12) return { id: '01', title: 'SYSTEM IDLE', desc: 'Sovereign compute at rest.' };
    if (progress < 0.35) return { id: '02', title: 'STRUCTURE REVEAL', desc: 'Exposing the architecture.' };
    if (progress < 0.60) return { id: '03', title: 'LAYERSTREAM', desc: 'Dynamic tensor flow.' };
    if (progress < 0.82) return { id: '04', title: 'FULL STACK', desc: 'Neural compute organism.' };
    return { id: '05', title: 'REASSEMBLY', desc: 'System locked and ready.' };
  }, [progress]);

  const show = progress > 0.03 && progress < 0.97;

  return (
    <motion.div
      animate={{ opacity: show ? 1 : 0 }}
      transition={{ duration: 0.4 }}
      style={{
        position: 'fixed', bottom: '64px', left: '50%', transform: 'translateX(-50%)',
        pointerEvents: 'none', zIndex: 50, display: 'flex',
        flexDirection: 'column', alignItems: 'center', textAlign: 'center',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '12px' }}>
        <div style={{ width: '28px', height: '1px', background: 'rgba(255,255,255,0.1)' }} />
        <span style={{
          fontSize: '10px', fontWeight: 900, letterSpacing: '0.2em',
          color: '#1D9E75', textTransform: 'uppercase' as const,
        }}>{data.id}</span>
        <div style={{ width: '28px', height: '1px', background: 'rgba(255,255,255,0.1)' }} />
      </div>
      <h3 style={{
        fontSize: 'clamp(24px, 4vw, 44px)', fontWeight: 800,
        letterSpacing: '-0.04em', marginBottom: '6px', color: '#fff',
      }}>{data.title}</h3>
      <p style={{
        fontSize: '10px', fontWeight: 800, letterSpacing: '0.15em',
        textTransform: 'uppercase' as const, color: 'rgba(255,255,255,0.2)',
      }}>{data.desc}</p>
    </motion.div>
  );
}