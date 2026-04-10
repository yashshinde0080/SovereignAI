'use client';

import { motion } from 'framer-motion';

export default function EngineSection() {
  return (
    <section id="engines" className="relative py-40 px-8 bg-sovereign-secondary/50">
      <div className="max-w-7xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          viewport={{ once: true }}
          className="text-center mb-20"
        >
          <p className="text-sovereign-teal text-sm font-semibold tracking-widest mb-4 uppercase">
            Dual Execution
          </p>
          <h2 className="text-6xl font-bold tracking-tighter">
            Dual execution. One system.
          </h2>
        </motion.div>

        <div className="grid md:grid-cols-2 gap-8">
          {/* FullRAM Engine */}
          <motion.div
            initial={{ opacity: 0, x: -40 }}
            whileInView={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            viewport={{ once: true }}
            className="p-12 bg-sovereign-black/50 backdrop-blur-sm rounded-3xl border border-white/5 hover:border-sovereign-indigo/30 transition-all"
          >
            <div className="w-16 h-16 bg-sovereign-indigo/20 rounded-2xl flex items-center justify-center mb-6">
              <svg className="w-8 h-8 text-sovereign-indigo" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <h3 className="text-3xl font-bold mb-4 tracking-tight">FullRAM</h3>
            <p className="text-white/60 text-lg leading-relaxed mb-6">
              Maximum performance mode. Entire model loaded into system memory. 
              Zero latency. Pure speed.
            </p>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 bg-sovereign-teal rounded-full" />
                <span className="text-white/50">Instant token generation</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 bg-sovereign-teal rounded-full" />
                <span className="text-white/50">No streaming overhead</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 bg-sovereign-teal rounded-full" />
                <span className="text-white/50">Hardware-native execution</span>
              </div>
            </div>
          </motion.div>

          {/* LayerStream Engine */}
          <motion.div
            initial={{ opacity: 0, x: 40 }}
            whileInView={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, delay: 0.4 }}
            viewport={{ once: true }}
            className="p-12 bg-sovereign-black/50 backdrop-blur-sm rounded-3xl border border-white/5 hover:border-sovereign-teal/30 transition-all"
          >
            <div className="w-16 h-16 bg-sovereign-teal/20 rounded-2xl flex items-center justify-center mb-6">
              <svg className="w-8 h-8 text-sovereign-teal" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
              </svg>
            </div>
            <h3 className="text-3xl font-bold mb-4 tracking-tight">LayerStream</h3>
            <p className="text-white/60 text-lg leading-relaxed mb-6">
              Memory-efficient streaming. Model layers loaded dynamically from storage. 
              Runs where others fail.
            </p>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 bg-sovereign-indigo rounded-full" />
                <span className="text-white/50">Minimal RAM footprint</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 bg-sovereign-indigo rounded-full" />
                <span className="text-white/50">SSD/USB-based execution</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 bg-sovereign-indigo rounded-full" />
                <span className="text-white/50">Infinite model scale</span>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}