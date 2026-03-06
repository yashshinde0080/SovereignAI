"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { motion, type Variants } from "framer-motion";
import { Mail, MessageSquare, Send, Hexagon, Activity, ShieldCheck, Cpu, Zap, Globe } from "lucide-react";
import { useState } from "react";

const containerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0.1 },
  },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 10 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: "easeOut" },
  },
};

export function ContactFormSection() {
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    message: "",
  });

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
  };

  const handleChange = (
    event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    setFormData((prev) => ({
      ...prev,
      [event.target.name]: event.target.value,
    }));
  };

  return (
    <section className="relative w-full flex flex-col p-0 h-full">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        className="mb-6 relative z-10"
      >
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-mono text-[10px] font-bold uppercase tracking-[0.2em] mb-6 shadow-[0_0_15px_rgba(16,185,129,0.15)]">
          <Hexagon className="w-3.5 h-3.5 fill-emerald-500/20" /> SECURE CHANNEL
        </div>
        <h2 className="text-4xl lg:text-5xl font-black tracking-[-0.04em] text-white mb-4 leading-[0.9]">
          Initialize <br/><span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-emerald-600">Node Sync.</span>
        </h2>
        <p className="text-zinc-400 text-sm font-medium leading-[1.6]">
          Establish a direct cryptographic link to our core team. Expect response within standard operational parameters (24h).
        </p>
      </motion.div>

      {/* Mini Fibonacci Grid Overlay Data */}
      <motion.div 
        initial={{ opacity: 0, y: 10 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ delay: 0.2 }}
        className="grid grid-cols-3 grid-rows-2 gap-3 mb-8 w-full relative z-10"
      >
        {/* Block 02 */}
        <div className="col-span-2 row-span-2 flex flex-col justify-between p-5 rounded-3xl bg-zinc-950 border border-white/5 border-l-emerald-500/50 shadow-2xl group hover:border-emerald-500/30 transition-all overflow-hidden relative">
           <div className="absolute inset-0 bg-gradient-to-tr from-emerald-500/5 to-transparent pointer-events-none" />
           <div className="flex items-center justify-between text-zinc-400 mb-4 relative z-10">
             <div className="flex items-center gap-2">
               <div className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
               </div>
               <span className="text-[10px] font-mono uppercase tracking-widest font-bold">Network Status</span>
             </div>
             <span className="text-zinc-700 font-mono text-[10px] font-bold">02</span>
           </div>
           <div className="relative z-10">
             <span className="text-white font-black text-3xl flex items-center gap-2 mb-1">
                 Optimal <Activity className="w-6 h-6 text-emerald-500/50" />
             </span>
             <p className="text-zinc-500 text-xs font-medium mt-1">Decentralized nodes functioning securely via encrypted channels.</p>
           </div>
        </div>

        {/* Block 01 - A */}
        <div className="col-span-1 row-span-1 flex flex-col justify-center p-4 rounded-3xl bg-zinc-950 border border-white/5 border-t-indigo-500/50 shadow-xl group hover:border-indigo-500/30 transition-all relative overflow-hidden">
           <div className="absolute inset-0 bg-gradient-to-b from-indigo-500/5 to-transparent pointer-events-none" />
           <div className="flex items-center justify-between text-zinc-400 mb-1 relative z-10">
             <div className="flex items-center gap-1">
               <ShieldCheck className="w-3.5 h-3.5 text-indigo-500" />
               <span className="text-[9px] font-mono uppercase tracking-widest font-bold hidden sm:inline">Encrypt</span>
             </div>
             <span className="text-zinc-700 font-mono text-[9px] font-bold">01</span>
           </div>
           <span className="text-white font-bold text-sm sm:text-base relative z-10">Active TLS</span>
        </div>

        {/* Block 01 - B */}
        <div className="col-span-1 row-span-1 flex flex-col justify-center p-4 rounded-3xl bg-zinc-950 border border-white/5 border-b-rose-500/50 shadow-xl group hover:border-rose-500/30 transition-all relative overflow-hidden">
           <div className="absolute inset-0 bg-gradient-to-t from-rose-500/5 to-transparent pointer-events-none" />
           <div className="flex items-center justify-between text-zinc-400 mb-1 relative z-10">
             <div className="flex items-center gap-1">
               <Cpu className="w-3.5 h-3.5 text-rose-500" />
               <span className="text-[9px] font-mono uppercase tracking-widest font-bold hidden sm:inline">Load</span>
             </div>
             <span className="text-zinc-700 font-mono text-[9px] font-bold">01</span>
           </div>
           <span className="text-white font-bold text-sm sm:text-base relative z-10">24.5% Avg</span>
        </div>
      </motion.div>

      <motion.form
        onSubmit={handleSubmit}
        variants={containerVariants}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true }}
        className="flex flex-col gap-4 relative z-10"
      >
        <motion.div variants={itemVariants} className="space-y-1.5">
          <Label htmlFor="name" className="text-[10px] font-bold uppercase tracking-[0.15em] text-zinc-500 ml-1">
            Operator Name
          </Label>
          <Input
            id="name"
            name="name"
            placeholder="System Agent"
            value={formData.name}
            onChange={handleChange}
            className="h-12 rounded-2xl border-white/5 bg-zinc-900/50 text-white placeholder:text-zinc-600 focus-visible:ring-1 focus-visible:ring-emerald-500/30 focus-visible:border-emerald-500/50 transition-all font-mono text-sm px-4 shadow-inner"
            required
          />
        </motion.div>

        <motion.div variants={itemVariants} className="space-y-1.5">
          <Label htmlFor="email" className="text-[10px] font-bold uppercase tracking-[0.15em] text-zinc-500 ml-1">
            Return Address
          </Label>
          <div className="relative">
            <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <Input
              id="email"
              name="email"
              type="email"
              placeholder="agent@network.com"
              value={formData.email}
              onChange={handleChange}
              className="h-12 pl-12 rounded-2xl border-white/5 bg-zinc-900/50 text-white placeholder:text-zinc-600 focus-visible:ring-1 focus-visible:ring-emerald-500/30 focus-visible:border-emerald-500/50 transition-all font-mono text-sm shadow-inner"
              required
            />
          </div>
        </motion.div>

        <motion.div variants={itemVariants} className="space-y-1.5">
          <Label htmlFor="message" className="text-[10px] font-bold uppercase tracking-[0.15em] text-zinc-500 ml-1">
            Encrypted Payload
          </Label>
          <div className="relative">
            <MessageSquare className="absolute left-4 top-4 w-4 h-4 text-zinc-500" />
            <Textarea
              id="message"
              name="message"
              placeholder="State your operational parameters and required deployment architecture..."
              value={formData.message}
              onChange={handleChange}
              className="min-h-[100px] pl-12 pt-3 rounded-2xl border-white/5 bg-zinc-900/50 text-white placeholder:text-zinc-600 focus-visible:ring-1 focus-visible:ring-emerald-500/30 focus-visible:border-emerald-500/50 transition-all font-mono text-sm resize-none shadow-inner"
              required
            />
          </div>
        </motion.div>

        <motion.div variants={itemVariants} className="pt-2">
          <Button
            type="submit"
            className="w-full h-12 rounded-2xl bg-white text-black font-extrabold text-sm uppercase tracking-widest hover:bg-zinc-200 hover:scale-[1.02] transition-all duration-300 shadow-[0_0_30px_rgba(255,255,255,0.1)] group flex items-center justify-center gap-3"
          >
            Transmit Payload
            <Send className="w-4 h-4 group-hover:translate-x-1 group-hover:-translate-y-1 transition-transform" />
          </Button>
        </motion.div>
      </motion.form>

      {/* Bottom Mini-Fibonacci Action grid to fill empty space dynamically */}
      <motion.div 
        initial={{ opacity: 0, y: 10 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ delay: 0.3 }}
        className="grid grid-cols-2 grid-rows-2 gap-3 mt-6 w-full relative z-10 flex-1 min-h-[200px]"
      >
        {/* Contact Info Block / Data Hub */}
        <div className="col-span-1 row-span-2 flex flex-col justify-between p-5 rounded-3xl bg-emerald-500 border border-emerald-400 text-emerald-950 shadow-xl group hover:shadow-[0_0_30px_rgba(16,185,129,0.3)] transition-all relative overflow-hidden">
           <div className="flex items-center justify-between relative z-10 w-full mb-4">
             <div className="w-8 h-8 flex items-center justify-center bg-black/10 rounded-xl group-hover:scale-110 transition-transform">
               <Globe className="w-4 h-4 text-black" />
             </div>
             <span className="text-emerald-700 font-mono text-[9px] font-bold tracking-wider">03</span>
           </div>
           <div className="relative z-10 mt-auto">
             <span className="font-black text-2xl lg:text-3xl tracking-tighter block leading-none">Global</span>
             <span className="text-[9px] font-bold uppercase tracking-widest text-emerald-800 mt-1 block">Edge Network</span>
           </div>
           <div className="absolute -bottom-6 -right-6 w-32 h-32 bg-white/20 blur-[40px] rounded-full group-hover:scale-150 transition-transform duration-700 pointer-events-none" />
        </div>

        {/* Priority SLA Block */}
        <div className="col-span-1 row-span-1 flex flex-col justify-between p-4 rounded-3xl bg-indigo-600 border border-indigo-500 text-white shadow-xl group hover:shadow-[0_0_30px_rgba(79,70,229,0.4)] transition-all relative overflow-hidden">
           <div className="flex items-center justify-between relative z-10 w-full mb-1">
             <Zap className="w-4 h-4 text-indigo-200 group-hover:text-white transition-colors" />
             <span className="text-indigo-300 font-mono text-[9px] font-bold tracking-wider">04</span>
           </div>
           <div className="relative z-10 w-full text-right mt-auto">
             <span className="font-black text-xl lg:text-2xl tracking-tighter block leading-none">99.99%</span>
             <span className="text-[9px] font-bold uppercase tracking-widest text-indigo-300">Uptime SLA</span>
           </div>
           <div className="absolute bottom-0 left-0 w-full opacity-20 pointer-events-none group-hover:opacity-40 transition-opacity">
               <svg viewBox="0 0 100 30" preserveAspectRatio="none" className="w-full h-12">
                 <path d="M0,30 Q25,0 50,30 T100,30 L100,50 L0,50 Z" fill="white" />
               </svg>
           </div>
        </div>

        {/* Tier-1 Hardware block */}
        <div className="col-span-1 row-span-1 flex flex-col justify-between p-4 rounded-3xl bg-zinc-950 border border-white/5 shadow-xl group hover:bg-zinc-900 transition-all cursor-pointer relative overflow-hidden">
           <div className="flex items-center justify-between relative z-10 w-full mb-1">
             <Cpu className="w-4 h-4 text-zinc-500 group-hover:text-emerald-500 transition-colors" />
             <span className="text-zinc-700 font-mono text-[9px] font-bold tracking-wider">05</span>
           </div>
           <div className="relative z-10 w-full text-right mt-auto">
             <span className="font-black text-xl lg:text-2xl tracking-tighter block leading-none text-zinc-300 group-hover:text-white">Tier-1</span>
             <span className="text-[9px] font-bold uppercase tracking-widest text-zinc-500 group-hover:text-zinc-400 mt-1 block">Hardware</span>
           </div>
        </div>
      </motion.div>
    </section>
  );
}
