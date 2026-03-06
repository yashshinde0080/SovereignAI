"use client";

import { motion, Variants } from "framer-motion";
import { 
  ArrowUpRight, 
  BrainCircuit, 
  ShieldAlert, 
  Cpu, 
  Zap, 
  Network,
  Activity
} from "lucide-react";
import Link from "next/link";

export default function FibonacciLanding() {
  const container: Variants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.15,
        delayChildren: 0.2,
      },
    },
  };

  const item: Variants = {
    hidden: { opacity: 0, scale: 0.95, y: 20 },
    show: { 
      opacity: 1, 
      scale: 1, 
      y: 0,
      transition: { type: "spring", stiffness: 100, damping: 20 }
    },
  };

  return (
    <div className="relative min-h-[800px] w-full bg-[#030303] text-zinc-100 font-sans overflow-hidden">
      {/* Dynamic Background */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] rounded-[100%] bg-indigo-600/10 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] rounded-[100%] bg-emerald-600/10 blur-[120px]" />
        <div className="absolute top-[20%] right-[30%] w-[30%] h-[30%] rounded-[100%] bg-rose-600/10 blur-[100px]" />
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-15 mix-blend-overlay" />
      </div>

      <main className="relative z-10 w-full h-full flex flex-col p-4 md:p-8">
        {/* Superior Header */}
        <header className="flex justify-between items-center mb-10 w-full shrink-0">
          <motion.div 
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
            className="flex items-center gap-3"
          >
            <div className="w-10 h-10 rounded-full bg-white flex items-center justify-center shadow-[0_0_20px_rgba(255,255,255,0.2)]">
              <span className="text-black font-black text-xl tracking-tighter">S</span>
            </div>
            <span className="font-bold text-2xl tracking-tighter hidden md:block text-zinc-100 hover:text-white transition-colors cursor-pointer">
              SovereignAI<span className="text-emerald-500">.</span>
            </span>
          </motion.div>
          <motion.nav 
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1], delay: 0.1 }}
            className="hidden md:flex items-center gap-10 text-xs font-semibold text-zinc-400 uppercase tracking-[0.2em]"
          >
            {['Platform', 'Intelligence', 'Security', 'Company'].map((link) => (
              <Link key={link} href="#" className="hover:text-white transition-colors relative group py-2">
                {link}
                <span className="absolute bottom-0 left-0 w-full h-px bg-white/0 transition-colors group-hover:bg-white" />
              </Link>
            ))}
          </motion.nav>
          <motion.button
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1], delay: 0.2 }}
            className="px-6 py-3 rounded-full bg-white text-black font-semibold text-sm hover:bg-zinc-200 transition-colors active:scale-95 shadow-xl flex items-center gap-2"
          >
            Connect Node <ArrowUpRight className="w-4 h-4 opacity-70" />
          </motion.button>
        </header>

        {/* Mathematical Fibonacci 8x5 Grid - Strictly Enforced Structure */}
        <motion.div 
          variants={container}
          initial="hidden"
          animate="show"
          className="flex-1 w-full grid grid-cols-1 md:grid-cols-8 md:grid-rows-5 gap-4 auto-rows-[250px] md:auto-rows-auto md:min-h-[600px] xl:min-h-[700px] pb-10"
        >
          {/* Fibonacci Block 1: 5x5 Grid Area */}
          <motion.div 
            variants={item}
            className="md:col-start-1 md:col-end-6 md:row-start-1 md:row-end-6 rounded-[2rem] bg-zinc-900 border border-white/10 p-8 lg:p-12 flex flex-col justify-between relative overflow-hidden group hover:border-white/20 transition-all duration-500 shadow-2xl h-full"
          >
            {/* Superior Inner Glow Effects */}
            <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/10 via-transparent to-black/80 opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" />
            
            <div className="relative z-20 flex justify-between items-start">
              <div className="px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 tracking-widest text-[10px] font-bold font-mono inline-flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_10px_rgba(16,185,129,0.8)]" />
                SYSTEM NEURAL LINK ACTIVE
              </div>
              <span className="text-zinc-600 font-mono text-xs font-bold font-m">05</span>
            </div>

            <div className="relative z-20 mt-auto pt-8">
              <h1 className="text-6xl md:text-7xl lg:text-8xl xl:text-[8.5rem] font-black tracking-[-0.04em] leading-[0.85] mb-8 drop-shadow-2xl text-white">
                Unleash <br/>
                <span className="text-transparent bg-clip-text bg-gradient-to-br from-zinc-200 via-zinc-400 to-zinc-600">
                  Autonomy.
                </span>
              </h1>
              <p className="text-lg text-zinc-400 max-w-md font-medium leading-[1.6] mb-10">
                The absolute pinnacle of sovereign artificial intelligence. Fully decentralized architecture, cryptographically secure edge-processing, and entirely under your direct command.
              </p>
              
              <div className="flex flex-wrap gap-4 pb-2">
                <button className="h-14 px-8 rounded-full bg-white text-black font-bold flex items-center gap-3 hover:scale-105 hover:bg-zinc-100 transition-all duration-300 shadow-[0_0_30px_rgba(255,255,255,0.15)] group shrink-0">
                  Deploy Instance <ArrowUpRight className="w-5 h-5 group-hover:translate-x-1 group-hover:-translate-y-1 transition-transform" />
                </button>
              </div>
            </div>

            {/* Geometric Decorative Element */}
            <div className="absolute -right-[20%] -top-[20%] w-[100%] h-[150%] pointer-events-none opacity-30 mix-blend-screen overflow-hidden z-10 transition-transform duration-1000 group-hover:scale-[1.05]">
                <svg viewBox="0 0 100 100" className="absolute right-0 top-0 w-full h-full animate-[spin_120s_linear_infinite]">
                  <path d="M50 50 m -45, 0 a 45,45 0 1,0 90,0 a 45,45 0 1,0 -90,0" fill="none" stroke="url(#g1)" strokeWidth="0.2" className="text-white" strokeDasharray="1 3"/>
                  <path d="M50 50 m -35, 0 a 35,35 0 1,0 70,0 a 35,35 0 1,0 -70,0" fill="none" stroke="currentColor" strokeWidth="0.3" className="text-indigo-400/30" strokeDasharray="3 6"/>
                  <path d="M50 50 m -25, 0 a 25,25 0 1,0 50,0 a 25,25 0 1,0 -50,0" fill="none" stroke="currentColor" strokeWidth="0.5" className="text-emerald-400/20" strokeDasharray="6 12"/>
                  <defs>
                    <linearGradient id="g1" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stopColor="#fff" stopOpacity="0.8"/>
                      <stop offset="100%" stopColor="#818cf8" stopOpacity="0"/>
                    </linearGradient>
                  </defs>
                </svg>
            </div>
          </motion.div>

          {/* Fibonacci Block 2: 3x3 Grid Area */}
          <motion.div 
            variants={item}
            className="md:col-start-6 md:col-end-9 md:row-start-1 md:row-end-4 rounded-[2rem] bg-zinc-950 border border-white/10 p-8 flex flex-col justify-between relative overflow-hidden group hover:border-white/20 transition-all duration-500 shadow-xl"
          >
            <div className="absolute inset-0 bg-gradient-to-tr from-rose-500/10 via-black to-black opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" />
            
            <div className="flex justify-between items-start relative z-20">
              <div className="w-14 h-14 rounded-2xl border border-white/10 flex items-center justify-center bg-white/5 backdrop-blur-xl group-hover:bg-white/10 transition-colors">
                <BrainCircuit className="w-6 h-6 text-zinc-100" />
              </div>
              <span className="text-zinc-700 font-mono text-xs font-bold">03</span>
            </div>
            
            <div className="relative z-20 mt-16">
              <h3 className="text-3xl font-black mb-3 tracking-tighter text-white">Neural Core</h3>
              <p className="text-zinc-400 text-sm leading-relaxed max-w-[90%]">Proprietary quantum-resilient reasoning models engineered specifically for multi-step asymmetric tasks.</p>
            </div>
            
            <div className="absolute top-2 right-2 text-zinc-800/30 group-hover:text-rose-500/10 transition-colors">
              <Network className="w-48 h-48" />
            </div>
          </motion.div>

          {/* Fibonacci Block 3: 2x2 Grid Area */}
          <motion.div 
            variants={item}
            className="md:col-start-6 md:col-end-8 md:row-start-4 md:row-end-6 rounded-[2rem] bg-emerald-500 border border-emerald-400 text-emerald-950 p-6 lg:p-8 flex flex-col justify-between relative overflow-hidden group hover:bg-emerald-400 hover:shadow-[0_0_40px_rgba(16,185,129,0.3)] transition-all duration-500"
          >
            <div className="flex justify-between items-start relative z-20">
              <div className="w-12 h-12 flex items-center justify-center bg-black/10 rounded-2xl group-hover:scale-110 transition-transform">
                <ShieldAlert className="w-6 h-6 text-black" />
              </div>
              <span className="text-emerald-700 font-mono text-xs font-bold">02</span>
            </div>
            <div className="relative z-20">
              <h3 className="text-4xl font-black leading-[0.9] tracking-tighter">Zero-Trust<br/>Vault</h3>
            </div>
            
            {/* Visual element for block 02 */}
            <div className="absolute -bottom-8 -right-8 w-40 h-40 bg-white/20 blur-[50px] rounded-full group-hover:scale-150 transition-transform duration-700 pointer-events-none" />
          </motion.div>

          {/* Fibonacci Block 4: 1x1 Grid Area A */}
          <motion.div 
            variants={item}
            className="md:col-start-8 md:col-end-9 md:row-start-4 md:row-end-5 rounded-[2rem] bg-indigo-600 border border-indigo-500 p-6 flex flex-col justify-between relative overflow-hidden group hover:bg-indigo-500 hover:shadow-[0_0_30px_rgba(79,70,229,0.4)] transition-all duration-300"
          >
            <div className="flex justify-between items-start w-full relative z-20">
                <Zap className="w-5 h-5 text-indigo-200 opacity-90 group-hover:scale-110 transition-transform" />
                <span className="text-indigo-800 font-mono text-[10px] font-bold">01</span>
            </div>
            <div className="relative z-20 text-center w-full mt-2">
                <div className="font-black text-3xl text-white tracking-tighter mb-1">0.2s</div>
                <div className="text-[10px] text-indigo-200 font-medium tracking-widest uppercase">Cold Start</div>
            </div>
            {/* Background waveform */}
            <div className="absolute bottom-0 left-0 w-full opacity-20 pointer-events-none group-hover:opacity-40 transition-opacity">
               <svg viewBox="0 0 100 30" preserveAspectRatio="none" className="w-full h-12">
                 <path d="M0,30 Q25,0 50,30 T100,30 L100,50 L0,50 Z" fill="white" />
               </svg>
            </div>
          </motion.div>

          {/* Fibonacci Block 5: 1x1 Grid Area B */}
          <motion.div 
            variants={item}
            className="md:col-start-8 md:col-end-9 md:row-start-5 md:row-end-6 rounded-[2rem] bg-zinc-900 border border-zinc-800 p-6 flex flex-col justify-between relative overflow-hidden group hover:bg-white transition-all duration-500 cursor-pointer"
          >
            <div className="flex justify-between items-start w-full relative z-20">
                <Cpu className="w-5 h-5 text-zinc-400 group-hover:text-black transition-colors" />
                <span className="text-zinc-800 group-hover:text-zinc-300 font-mono text-[10px] font-bold transition-colors">01</span>
            </div>
            
            <div className="relative z-20 flex flex-col items-center mt-2 group-hover:scale-110 transition-transform duration-500">
                <Activity className="w-6 h-6 mb-1 text-emerald-500 opacity-0 group-hover:opacity-100 transition-opacity absolute -top-8" />
                <span className="font-black text-3xl text-white group-hover:text-black transition-colors tracking-tighter">H100</span>
                <div className="text-[10px] text-zinc-500 group-hover:text-zinc-600 font-medium tracking-widest uppercase mt-1">Native GPU</div>
            </div>
            <div className="absolute inset-0 bg-gradient-to-b from-transparent to-white/5 opacity-0 group-hover:opacity-100 transition-opacity" />
          </motion.div>

        </motion.div>
      </main>
    </div>
  );
}

