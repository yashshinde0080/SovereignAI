"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import Image from "next/image";
import { motion } from "framer-motion";
import { ArrowRight, CheckCircle2, Play, Sparkles, Zap } from "lucide-react";
import { useState } from "react";

const benefits = [
  "No operational friction",
  "Scale autonomously",
  "Zero-trust environment",
];

export function CTAHeroBlock() {
  const [email, setEmail] = useState("");
  const [isVideoHovered, setIsVideoHovered] = useState(false);

  return (
    <section className="relative w-full h-full flex flex-col justify-center overflow-hidden bg-transparent px-4 py-8 lg:py-12">
      {/* Animated background elements */}
      <div className="absolute inset-0 -z-10 overflow-hidden pointer-events-none">
        <motion.div
          animate={{
            scale: [1, 1.2, 1],
            rotate: [0, 180, 360],
            opacity: [0.1, 0.2, 0.1],
          }}
          transition={{ duration: 25, repeat: Infinity, ease: "linear" }}
          className="absolute -right-1/4 -top-1/4 h-96 w-96 rounded-full bg-emerald-500/10 blur-3xl md:h-[600px] md:w-[600px]"
        />
        <motion.div
          animate={{
            scale: [1.2, 1, 1.2],
            rotate: [360, 180, 0],
            opacity: [0.1, 0.2, 0.1],
          }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
          className="absolute -bottom-1/4 -left-1/4 h-96 w-96 rounded-full bg-indigo-500/10 blur-3xl md:h-[600px] md:w-[600px]"
        />
      </div>

      <div className="mx-auto max-w-7xl h-full flex items-center">
        <div className="grid gap-8 lg:grid-cols-2 lg:gap-12 items-center w-full">
          {/* Left side - Content */}
          <motion.div
            initial={{ opacity: 0, x: -50 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, ease: [0.6, 0.05, 0.01, 0.9] }}
            className="flex flex-col justify-center h-full"
          >
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <Badge className="mb-4 md:mb-6 font-mono border-emerald-500/20 bg-emerald-500/10 text-emerald-400 backdrop-blur-sm px-4 py-1.5 uppercase tracking-[0.2em] text-[10px]" variant="outline">
                <Sparkles className="mr-2 h-3.5 w-3.5 text-emerald-400" />
                Network Upgrade
              </Badge>
            </motion.div>

            <motion.h1
              className="mb-4 bg-clip-text text-4xl font-black tracking-tighter text-white md:mb-6 md:text-5xl lg:text-6xl"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
            >
              Sovereign Portable.{" "}
              <span className="bg-gradient-to-r from-emerald-400 to-emerald-600 bg-clip-text text-transparent">
                Intelligence System
              </span>
            </motion.h1>

            <motion.p
              className="mb-6 text-base text-zinc-400 md:mb-8 md:text-lg lg:text-xl font-medium"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
            >
              "A sovereign, portable AI compute environment that runs anywhere without installation or internet. Built for true air-gapped deployments with zero cloud dependency, zero telemetry, and enterprise-grade security"
            </motion.p>

            {/* Email signup form */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
              className="mb-6 md:mb-8"
            >
              <div className="flex flex-col gap-3 sm:flex-row">
                <Input
                  type="email"
                  placeholder="Join us in the AI Revolution.............."
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="h-12 flex-1 text-base md:h-14 bg-zinc-900/50 border-white/10 text-white placeholder:text-zinc-600 focus-visible:ring-emerald-500 focus-visible:ring-1"
                />
                <Button size="lg" className="group h-12 md:h-14 bg-emerald-500 text-black font-bold hover:bg-emerald-400 transition-colors">
                  <Zap className="mr-2 h-4 w-4" />
                  Download
                  <motion.div
                    className="ml-2"
                    animate={{ x: [0, 5, 0] }}
                    transition={{ repeat: Infinity, duration: 1.5 }}
                  >
                    <ArrowRight className="h-4 w-4" />
                  </motion.div>
                </Button>
              </div>
            </motion.div>

            {/* Benefits list */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.6 }}
              className="flex flex-wrap gap-4 md:gap-6"
            >
              {benefits.map((benefit, index) => (
                <motion.div
                  key={benefit}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.7 + index * 0.1 }}
                  className="flex items-center gap-2"
                >
                  <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                  <span className="text-sm font-medium text-zinc-400 md:text-base">
                    {benefit}
                  </span>
                </motion.div>
              ))}
            </motion.div>

            {/* Social proof */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.9 }}
              className="mt-8 flex flex-wrap items-center gap-4 md:mt-12 bg-zinc-900/30 w-fit p-3 rounded-2xl border border-white/5"
            >
              <div className="flex -space-x-2 pl-2">
                {[1, 2, 3, 4].map((i) => (
                  <motion.div
                    key={i}
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ delay: 1 + i * 0.1, type: "spring" }}
                    className="h-10 w-10 overflow-hidden rounded-full border-2 border-black bg-zinc-800"
                  >
                    <Image
                      src={`https://api.dicebear.com/7.x/avataaars/svg?seed=nodeuser${i}&backgroundColor=18181b`}
                      alt={`User ${i}`}
                      width={40}
                      height={40}
                      unoptimized
                      className="h-full w-full object-cover"
                    />
                  </motion.div>
                ))}
              </div>
              <div className="text-sm pr-4">
                <span className="font-bold text-white tracking-tight">10,000+</span>
                <span className="text-zinc-500 font-medium"> Models Integrated with Hugging Face</span>
              </div>
            </motion.div>
          </motion.div>

          {/* Right side - Video/Visual */}
          <motion.div
            initial={{ opacity: 0, x: 50 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, ease: [0.6, 0.05, 0.01, 0.9] }}
            className="flex items-center justify-center h-full mt-10 lg:mt-0"
          >
            <motion.div
              onHoverStart={() => setIsVideoHovered(true)}
              onHoverEnd={() => setIsVideoHovered(false)}
              className="relative w-full max-w-lg cursor-pointer group"
            >
              <Card className="relative overflow-hidden border-white/10 bg-zinc-900/30 p-2 shadow-2xl backdrop-blur-sm rounded-3xl">
                <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/10 via-transparent to-indigo-500/10 opacity-30 mix-blend-screen" />
                <motion.div
                  className="relative aspect-video overflow-hidden rounded-2xl bg-black border border-white/10"
                  whileHover={{ scale: 1.01 }}
                  transition={{ duration: 0.3 }}
                >
                  <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 mix-blend-overlay" />
                  
                  {/* Hexagon pattern background */}
                  <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyOCIgaGVpZ2h0PSI0OSIgdmlld0JveD0iMCAwIDI4IDQ5Ij4KICA8ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPgogICAgPHBhdGggZD0iTTEzLjk5IDIyTDcgMTJWMGw3IDEwTDcuMSAyMGwtNyAxMEMwIDMwLjEgMS4zIDIwLjEgMS4zMSAyMEwxMy45OSAyMi4xbDYuMSAxMFYyMGw2LTEwTDIxIDBE1IgPSJzZWNvbmQiIC8+CiAgICA8cGF0aCBkPSJNMTMuOTkgMjVMMSAzNWwyMiAybDUuMS0xN0wyMSA0NSBMNyA0NWwtNy0xMGw3LTEwTDEzLjk5IDI1eiIvPgogIDwvZz4KPC9zdmc+')] opacity-[0.03] animate-[spin_100s_linear_infinite]" />
                  
                  {/* Video thumbnail Inner visual */}
                  <div className="absolute inset-0 flex flex-col items-center justify-center bg-gradient-to-br from-emerald-500/5 to-transparent">
                    <motion.div
                      animate={
                        isVideoHovered
                          ? { scale: 1.1, rotate: 0 }
                          : { scale: 1, rotate: 0 }
                      }
                      transition={{ duration: 0.3 }}
                      className="relative z-20"
                    >
                      <motion.div
                        className="absolute inset-0 rounded-full bg-emerald-500/30 blur-2xl"
                        animate={{ scale: [1, 1.4, 1] }}
                        transition={{ duration: 2, repeat: Infinity }}
                      />
                      <div className="relative flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500 shadow-[0_0_30px_rgba(16,185,129,0.5)] md:h-20 md:w-20 border border-emerald-400">
                        <Play className="ml-1 h-8 w-8 text-black md:h-10 md:w-10 fill-black" />
                      </div>
                    </motion.div>
                    <div className="mt-6 text-sm font-mono text-zinc-500 tracking-widest uppercase relative z-20">Secure Operations</div>
                  </div>

                  {/* Floating elements */}
                  <motion.div
                    className="absolute right-4 top-4 rounded-xl bg-white/5 border border-white/10 p-2 shadow-2xl backdrop-blur-xl md:p-3"
                    animate={{ y: [0, -10, 0] }}
                    transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
                  >
                    <Zap className="h-4 w-4 text-emerald-400 md:h-5 md:w-5" />
                  </motion.div>

                  <motion.div
                    className="absolute bottom-4 left-4 rounded-xl bg-white/5 border border-white/10 p-2 shadow-2xl backdrop-blur-xl md:p-3"
                    animate={{ y: [0, 10, 0] }}
                    transition={{ duration: 5, repeat: Infinity, delay: 1, ease: "easeInOut" }}
                  >
                    <CheckCircle2 className="h-4 w-4 text-emerald-400 md:h-5 md:w-5" />
                  </motion.div>
                </motion.div>

                {/* Stats overlay */}
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 1.2 }}
                  className="mt-2 grid grid-cols-3 gap-2 p-1"
                >
                  {[
                    { label: "Queries", value: "3M+" },
                    { label: "Uptime", value: "99.9%" },
                    { label: "Nodes", value: "400+" },
                  ].map((stat, index) => (
                    <motion.div
                      key={stat.label}
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{
                        delay: 1.3 + index * 0.1,
                        type: "spring",
                      }}
                      className="rounded-xl bg-white/5 border border-white/5 p-2 text-center backdrop-blur-md hover:bg-white/10 transition-colors"
                    >
                      <div className="text-base font-black md:text-lg text-white font-mono">
                        {stat.value}
                      </div>
                      <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold">
                        {stat.label}
                      </div>
                    </motion.div>
                  ))}
                </motion.div>
              </Card>
            </motion.div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
