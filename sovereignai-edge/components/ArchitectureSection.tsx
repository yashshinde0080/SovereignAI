'use client';

import { motion } from 'framer-motion';

export default function ArchitectureSection() {
  return (
    <section id="architecture" className="relative py-40 px-8">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          viewport={{ once: true }}
          className="mb-20"
        >
          <p className="text-sovereign-indigo text-sm font-semibold tracking-widest mb-4 uppercase">
            System Architecture
          </p>
          <h2 className="text-6xl font-bold tracking-tighter mb-6">
            Built for constraint.
          </h2>
          <p className="text-2xl text-white/50 max-w-3xl leading-relaxed">
            Memory is not a limitation. Storage becomes compute.
          </p>
        </motion.div>

        <div className="space-y-6">
          {[
            {
              label: 'COMPUTE CORES',
              desc: 'Multi-threaded tensor processing',
              color: 'sovereign-indigo'
            },
            {
              label: 'MEMORY LAYERS',
              desc: 'Dynamic layer streaming from disk',
              color: 'sovereign-teal'
            },
            {
              label: 'KV CACHE',
              desc: 'Intelligent attention state management',
              color: 'sovereign-indigo'
            },
            {
              label: 'PIPELINE',
              desc: 'Zero-copy data flow architecture',
              color: 'sovereign-teal'
            }
          ].map((item, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -40 }}
              whileInView={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: i * 0.1 }}
              viewport={{ once: true }}
              className="group relative overflow-hidden"
            >
              <div className="flex items-center justify-between p-8 bg-sovereign-secondary/30 rounded-2xl border border-white/5 hover:border-white/10 transition-all">
                <div>
                  <h3 className={`text-xl font-bold mb-2 text-${item.color}`}>
                    {item.label}
                  </h3>
                  <p className="text-white/50">{item.desc}</p>
                </div>
                <div className={`w-12 h-12 rounded-full bg-${item.color}/20 flex items-center justify-center`}>
                  <div className={`w-3 h-3 rounded-full bg-${item.color}`} />
                </div>
              </div>
              <motion.div
                className={`absolute bottom-0 left-0 h-0.5 bg-${item.color}`}
                initial={{ width: 0 }}
                whileInView={{ width: '100%' }}
                transition={{ duration: 1, delay: i * 0.1 }}
                viewport={{ once: true }}
              />
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}