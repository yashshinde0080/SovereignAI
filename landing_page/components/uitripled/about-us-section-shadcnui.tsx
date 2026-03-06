"use client";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { motion, Variants } from "framer-motion";
import { Award, Heart, Target, Users, Sparkles, ChevronRight } from "lucide-react";

const values = [
  {
    icon: Target,
    title: "Our Mission",
    description:
      "To map the autonomous web and build the decentralized sovereign platform architecture of tomorrow.",
    color: "from-emerald-500/20 to-teal-500/5",
    iconColor: "text-emerald-400",
    gradient: "from-emerald-500/20"
  },
  {
    icon: Users,
    title: "Our Hive",
    description:
      "A collective of autonomous agents and visionary engineers building the future of sovereign compute.",
    color: "from-indigo-500/20 to-blue-500/5",
    iconColor: "text-indigo-400",
    gradient: "from-indigo-500/20"
  },
  {
    icon: Award,
    title: "Architecture",
    description:
      "Recognized for developing zero-trust, quantum-resilient reasoning models and resilient infrastructure.",
    color: "from-purple-500/20 to-fuchsia-500/5",
    iconColor: "text-purple-400",
    gradient: "from-purple-500/20"
  },
  {
    icon: Heart,
    title: "Alignment",
    description:
      "Total transparency and absolute commitment to our network nodes and their immutable security.",
    color: "from-rose-500/20 to-pink-500/5",
    iconColor: "text-rose-400",
    gradient: "from-rose-500/20"
  },
];

export function AboutUsSection() {
  const containerVariants: Variants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.15,
      },
    },
  };

  const itemVariants: Variants = {
    hidden: { opacity: 0, y: 30 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.6, ease: "easeOut" },
    },
  };

  return (
    <section className="bg-transparent px-4 py-8 md:py-16 relative overflow-hidden">
      
      {/* Abstract Background Orbs */}
      <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-zinc-800/20 rounded-full blur-[120px] mix-blend-screen pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-indigo-900/10 rounded-full blur-[100px] mix-blend-screen pointer-events-none" />

      <div className="mx-auto max-w-7xl relative z-10">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="mb-16 text-center"
        >
          <Badge variant="outline" className="mb-6 inline-flex items-center gap-2 rounded-full border-white/10 bg-white/5 px-4 py-1.5 text-xs uppercase tracking-[0.2em] text-zinc-400 backdrop-blur">
            <Sparkles className="w-3.5 h-3.5" /> Identity Core
          </Badge>
          <h2 className="mb-4 text-3xl font-black md:text-5xl lg:text-6xl tracking-tighter text-white">
            Who We Are
          </h2>
          <p className="mx-auto max-w-2xl text-lg text-zinc-400 font-medium">
            We are a decentralized intelligence protocol engineering the sovereign infrastructure of tomorrow.
          </p>
        </motion.div>

        <motion.div
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          className="grid gap-6 md:gap-8 md:grid-cols-2 lg:grid-cols-2"
        >
          {values.map((value) => {
            const Icon = value.icon;
            return (
              <motion.div key={value.title} variants={itemVariants}>
                <Card className="group relative h-full overflow-hidden border border-white/10 bg-zinc-900/40 backdrop-blur-xl p-8 transition-all hover:border-white/20 hover:shadow-2xl hover:-translate-y-1">
                  
                  {/* Hover Glow Background */}
                  <div className={`absolute inset-0 bg-gradient-to-br opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none ${value.color}`} />
                  
                  <div className="relative z-10">
                    <div className={`mb-6 inline-flex rounded-2xl bg-white/5 border border-white/10 p-4 shadow-inner group-hover:bg-black/20 transition-colors`}>
                      <Icon className={`h-6 w-6 ${value.iconColor} transition-transform duration-500 group-hover:scale-110`} />
                    </div>
                    <h3 className="mb-3 text-2xl font-bold text-white tracking-tight">{value.title}</h3>
                    <p className="text-zinc-400 leading-relaxed">{value.description}</p>
                  </div>

                  {/* Top Right Decorative Accent */}
                  <div className={`absolute -top-12 -right-12 w-32 h-32 bg-gradient-to-br ${value.gradient} to-transparent blur-2xl opacity-20 group-hover:opacity-50 transition-opacity duration-700`} />
                </Card>
              </motion.div>
            );
          })}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="mt-16 rounded-3xl border border-white/10 bg-gradient-to-b from-white/5 to-transparent p-10 md:p-12 text-center relative overflow-hidden group hover:border-white/20 transition-colors"
        >
          <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 mix-blend-overlay" />
          <div className="relative z-10 flex flex-col items-center">
            <h3 className="mb-4 text-3xl md:text-4xl font-black text-white tracking-tighter">Join Our Network</h3>
            <p className="mx-auto max-w-2xl text-zinc-400 mb-8 text-lg">
              We're always linking with talented node operators and neural architects to join our distributed team. Let's align our parameters.
            </p>
            <button className="flex items-center gap-2 px-8 py-4 bg-white text-black font-bold rounded-full hover:scale-105 hover:bg-zinc-200 transition-all">
                Initialize Connection <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
