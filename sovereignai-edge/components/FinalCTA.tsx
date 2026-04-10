'use client';

import { motion } from 'framer-motion';

export default function FinalCTA() {
  return (
    <section className="relative py-40 px-8">
      <div className="max-w-4xl mx-auto text-center">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          whileInView={{ opacity: 1, scale: 1 }}
          transition={{ duration: 1 }}
          viewport={{ once: true }}
        >
          <h2 className="text-7xl font-bold tracking-tighter mb-8">
            Run AI anywhere.
          </h2>
          <p className="text-2xl text-white/50 mb-12">
            Sovereign compute. No compromises.
          </p>

          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="px-12 py-5 bg-sovereign-indigo hover:bg-sovereign-indigo/90 rounded-full text-lg font-bold transition-all shadow-[0_0_40px_rgba(60,52,137,0.3)]"
          >
            Deploy SovereignAI Edge
          </motion.button>
        </motion.div>
      </div>

      {/* Footer */}
      <motion.footer
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        transition={{ duration: 0.8, delay: 0.3 }}
        viewport={{ once: true }}
        className="max-w-7xl mx-auto mt-32 pt-12 border-t border-white/5 text-center text-sm text-white/30"
      >
        <p>© 2024 SovereignAI. Infrastructure-grade compute.</p>
      </motion.footer>
    </section>
  );
}