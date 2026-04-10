'use client';

import { motion } from 'framer-motion';

export default function SecuritySection() {
  return (
    <section id="security" className="relative py-40 px-8 bg-sovereign-secondary/50">
      <div className="max-w-5xl mx-auto text-center">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          viewport={{ once: true }}
        >
          <div className="w-24 h-24 mx-auto mb-8 bg-sovereign-indigo/20 rounded-3xl flex items-center justify-center">
            <svg className="w-12 h-12 text-sovereign-indigo" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>

          <h2 className="text-6xl font-bold tracking-tighter mb-6">
            Nothing leaves the machine.
          </h2>

          <p className="text-2xl text-white/50 mb-16 max-w-2xl mx-auto leading-relaxed">
            Air-gapped capable. Zero telemetry. Your compute. Your sovereignty.
          </p>

          <div className="grid md:grid-cols-3 gap-8 text-left">
            {[
              { title: 'Offline-First', desc: 'No internet required. Ever.' },
              { title: 'Zero Telemetry', desc: 'Nothing tracked. Nothing sent.' },
              { title: 'Air-Gapped', desc: 'Runs in complete isolation.' }
            ].map((item, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: i * 0.15 }}
                viewport={{ once: true }}
                className="p-8 bg-sovereign-black/30 rounded-2xl border border-white/5"
              >
                <h3 className="text-xl font-bold mb-3">{item.title}</h3>
                <p className="text-white/50">{item.desc}</p>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  );
}