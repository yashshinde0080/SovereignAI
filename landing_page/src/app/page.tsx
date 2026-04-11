'use client';

import { useEffect } from 'react';
import Lenis from '@studio-freight/lenis';
import Navbar from '@/components/Navbar';
import Hero from '@/components/Hero';
import ScrollSequence from '@/components/ScrollSequence';
import EngineSection from '@/components/EngineSection';
import ArchitectureSection from '@/components/ArchitectureSection';
import SecuritySection from '@/components/SecuritySection';
import FinalCTA from '@/components/FinalCTA';

export default function Home() {
  // Initialize smooth scroll
  useEffect(() => {
    const lenis = new Lenis({
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      smoothWheel: true,
    });

    function raf(time: number) {
      lenis.raf(time);
      requestAnimationFrame(raf);
    }

    requestAnimationFrame(raf);

    return () => {
      lenis.destroy();
    };
  }, []);

  return (
    <main style={{ position: 'relative', background: '#050505', minHeight: '100vh' }}>
      <Navbar />
      <Hero />
      <ScrollSequence />
      <EngineSection />
      <ArchitectureSection />
      <SecuritySection />
      <FinalCTA />
    </main>
  );
}