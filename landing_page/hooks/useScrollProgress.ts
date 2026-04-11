'use client';

import { useEffect, useState } from 'react';

export function useScrollProgress(elementId?: string) {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const handleScroll = () => {
      if (elementId) {
        const element = document.getElementById(elementId);
        if (!element) return;

        const rect = element.getBoundingClientRect();
        const elementHeight = element.offsetHeight;
        const viewportHeight = window.innerHeight;
        
        // Calculate progress based on element's position
        const scrollStart = -rect.top;
        const scrollRange = elementHeight - viewportHeight;
        const scrollProgress = Math.max(0, Math.min(1, scrollStart / scrollRange));
        
        setProgress(scrollProgress);
      } else {
        // Global scroll progress
        const scrollTop = window.scrollY;
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        const scrollProgress = scrollTop / docHeight;
        
        setProgress(scrollProgress);
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll(); // Initial calculation

    return () => window.removeEventListener('scroll', handleScroll);
  }, [elementId]);

  return progress;
}