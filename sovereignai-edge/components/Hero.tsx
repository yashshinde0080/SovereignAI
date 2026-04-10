'use client';

import { motion } from 'framer-motion';

export default function Hero() {
  return (
    <section className="relative h-screen flex items-center justify-center overflow-hidden">
      {/* Background Gradient */}
      <div className="absolute inset-0">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[1200px] h-[600px] bg-sovereign-indigo/20 rounded-full blur-[150px]" />
      </div>

      {/* Content */}
      <div className="relative z-10 text-center px-8">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
        >
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2, duration: 0.8 }}
            className="text-sovereign-teal text-sm font-semibold tracking-widest mb-6 uppercase"
          >
            Sovereign Compute Infrastructure
          </motion.p>
          
          <h1 className="text-[clamp(3rem,8vw,7rem)] font-bold tracking-tighter leading-[0.9] mb-8">
            SovereignAI
            <br />
            <span className="text-white/40">Edge</span>
          </h1>

          <p className="text-2xl text-white/60 font-light tracking-tight max-w-2xl mx-auto mb-12">
            AI. Without dependency.
          </p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6, duration: 0.8 }}
            className="flex items-center justify-center gap-4"
          >
            <button className="px-8 py-4 bg-sovereign-indigo hover:bg-sovereign-indigo/90 rounded-full font-semibold transition-all hover:scale-105">
              Deploy Now
            </button>
            <button className="px-8 py-4 border border-white/10 hover:border-white/30 rounded-full font-semibold transition-all hover:scale-105">
              View Docs
            </button>
          </motion.div>
        </motion.div>

        {/* Scroll Indicator */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.2, duration: 1 }}
          className="absolute bottom-12 left-1/2 -translate-x-1/2"
        >
          <motion.div
            animate={{ y: [0, 10, 0] }}
            transition={{ repeat: Infinity, duration: 2, ease: 'easeInOut' }}
            className="w-6 h-10 border-2 border-white/20 rounded-full flex items-start justify-center p-2"
          >
            <motion.div className="w-1 h-2 bg-white/60 rounded-full" />
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}