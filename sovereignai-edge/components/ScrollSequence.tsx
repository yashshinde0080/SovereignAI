'use client';

import { useEffect, useRef, useState } from 'react';
import { ImagePreloader } from '@/utils/imagePreloader';
import { motion } from 'framer-motion';

const TOTAL_FRAMES = 120; // Adjust based on your actual frame count

export default function ScrollSequence() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [images, setImages] = useState<HTMLImageElement[]>([]);
  const [loadProgress, setLoadProgress] = useState(0);
  const [isLoaded, setIsLoaded] = useState(false);

  // Preload images
  useEffect(() => {
    const preloader = new ImagePreloader(TOTAL_FRAMES);
    
    preloader.preloadImages((progress) => {
      setLoadProgress(progress);
    }).then((loadedImages) => {
      setImages(loadedImages);
      setIsLoaded(true);
    });
  }, []);

  // Render canvas on scroll
  useEffect(() => {
    if (!isLoaded || images.length === 0) return;

    const canvas = canvasRef.current;
    const context = canvas?.getContext('2d');
    if (!canvas || !context) return;

    const renderFrame = () => {
      const container = containerRef.current;
      if (!container) return;

      const rect = container.getBoundingClientRect();
      const scrollProgress = Math.max(0, Math.min(1, -rect.top / (rect.height - window.innerHeight)));
      
      // Map scroll progress to frame index
      const frameIndex = Math.floor(scrollProgress * (images.length - 1));
      const img = images[frameIndex];

      if (!img) return;

      // Set canvas dimensions to match viewport
      const scale = window.devicePixelRatio || 1;
      canvas.width = window.innerWidth * scale;
      canvas.height = window.innerHeight * scale;
      canvas.style.width = `${window.innerWidth}px`;
      canvas.style.height = `${window.innerHeight}px`;

      context.scale(scale, scale);

      // Calculate aspect ratio fit
      const canvasAspect = canvas.width / canvas.height;
      const imgAspect = img.width / img.height;

      let drawWidth, drawHeight, offsetX, offsetY;

      if (canvasAspect > imgAspect) {
        drawWidth = canvas.width / scale;
        drawHeight = drawWidth / imgAspect;
        offsetX = 0;
        offsetY = (canvas.height / scale - drawHeight) / 2;
      } else {
        drawHeight = canvas.height / scale;
        drawWidth = drawHeight * imgAspect;
        offsetX = (canvas.width / scale - drawWidth) / 2;
        offsetY = 0;
      }

      context.clearRect(0, 0, canvas.width, canvas.height);
      context.drawImage(img, offsetX, offsetY, drawWidth, drawHeight);
    };

    const handleScroll = () => {
      requestAnimationFrame(renderFrame);
    };

    const handleResize = () => {
      renderFrame();
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    window.addEventListener('resize', handleResize);
    
    // Initial render
    renderFrame();

    return () => {
      window.removeEventListener('scroll', handleScroll);
      window.removeEventListener('resize', handleResize);
    };
  }, [isLoaded, images]);

  return (
    <div 
      ref={containerRef}
      id="scroll-sequence"
      className="relative w-full"
      style={{ height: '400vh' }}
    >
      {/* Loading State */}
      {!isLoaded && (
        <div className="fixed inset-0 flex items-center justify-center bg-sovereign-black z-50">
          <div className="text-center">
            <div className="w-64 h-1 bg-sovereign-secondary rounded-full overflow-hidden mb-4">
              <motion.div
                className="h-full bg-sovereign-indigo"
                initial={{ width: 0 }}
                animate={{ width: `${loadProgress}%` }}
              />
            </div>
            <p className="text-sm text-white/40 font-medium tracking-wide">
              INITIALIZING SYSTEM {Math.round(loadProgress)}%
            </p>
          </div>
        </div>
      )}

      {/* Sticky Canvas Container */}
      <div className="sticky top-0 left-0 w-full h-screen flex items-center justify-center overflow-hidden">
        <canvas
          ref={canvasRef}
          className="gpu-accelerated"
        />
        
        {/* Volumetric Glow Effect */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-sovereign-indigo/10 rounded-full blur-[120px]" />
        </div>
      </div>

      {/* Scroll-synced Copy */}
      <ScrollCopy containerRef={containerRef} />
    </div>
  );
}

// Scroll-synced text component
function ScrollCopy({ containerRef }: { containerRef: React.RefObject<HTMLDivElement> }) {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const handleScroll = () => {
      const container = containerRef.current;
      if (!container) return;

      const rect = container.getBoundingClientRect();
      const scrollProgress = Math.max(0, Math.min(1, -rect.top / (rect.height - window.innerHeight)));
      setProgress(scrollProgress);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();

    return () => window.removeEventListener('scroll', handleScroll);
  }, [containerRef]);

  const getCopyForProgress = () => {
    if (progress < 0.15) {
      return { title: 'SYSTEM IDLE', subtitle: 'Sovereign compute at rest' };
    } else if (progress < 0.40) {
      return { title: 'STRUCTURE REVEAL', subtitle: 'Exposing the architecture' };
    } else if (progress < 0.65) {
      return { title: 'LAYERSTREAM', subtitle: 'Memory flows through cores' };
    } else if (progress < 0.85) {
      return { title: 'FULL ARCHITECTURE', subtitle: 'Neural compute organism' };
    } else {
      return { title: 'REASSEMBLY', subtitle: 'System locked and ready' };
    }
  };

  const copy = getCopyForProgress();
  const opacity = progress > 0.02 && progress < 0.98 ? 1 : 0;

  return (
    <motion.div
      className="fixed bottom-24 left-1/2 -translate-x-1/2 text-center pointer-events-none z-10"
      animate={{ opacity }}
      transition={{ duration: 0.3 }}
    >
      <h3 className="text-4xl font-bold tracking-tighter mb-2">{copy.title}</h3>
      <p className="text-white/50 text-sm tracking-wide">{copy.subtitle}</p>
    </motion.div>
  );
}