'use client';

import { motion, useScroll, useTransform } from 'framer-motion';
import { useEffect, useState } from 'react';

export default function Navbar() {
  const [isScrolled, setIsScrolled] = useState(false);
  const { scrollY } = useScroll();
  
  const opacity = useTransform(scrollY, [0, 100], [0, 1]);
  const blur = useTransform(scrollY, [0, 100], [0, 10]);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 50);
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <motion.nav
      style={{ opacity }}
      className="fixed top-0 left-0 right-0 z-50 px-8 py-6"
    >
      <motion.div
        style={{
          backdropFilter: useTransform(blur, (v) => `blur(${v}px)`),
        }}
        className="max-w-[1800px] mx-auto flex items-center justify-between px-8 py-4 rounded-full bg-sovereign-secondary/40 border border-white/5"
      >
        {/* Logo */}
        <div className="flex items-center">
          <span className="text-lg font-bold tracking-tighter text-white">
            SovereignAI
          </span>
        </div>

        {/* Center Navigation */}
        <div className="hidden md:flex items-center gap-8 text-sm font-medium">
          <a href="#overview" className="text-white/60 hover:text-white transition-colors">
            Overview
          </a>
          <a href="#architecture" className="text-white/60 hover:text-white transition-colors">
            Architecture
          </a>
          <a href="#engines" className="text-white/60 hover:text-white transition-colors">
            Engines
          </a>
          <a href="#security" className="text-white/60 hover:text-white transition-colors">
            Security
          </a>
          <a href="#deploy" className="text-white/60 hover:text-white transition-colors">
            Deploy
          </a>
        </div>

        {/* CTA */}
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="px-6 py-2.5 bg-sovereign-indigo hover:bg-sovereign-indigo/90 rounded-full text-sm font-semibold transition-colors"
        >
          Launch System
        </motion.button>
      </motion.div>
    </motion.nav>
  );
}