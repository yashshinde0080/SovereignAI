"use client";

import { motion, type Variants } from "framer-motion";
import { ArrowUpRight, PlayCircle, Sparkles, Wand2, MonitorPlay, Focus, Layers, Box } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Image from "next/image";

interface AvatarProfile {
  src: string;
  alt: string;
}

interface Metric {
  label: string;
  value: string;
  caption: string;
}

interface ProcessStep {
  label: string;
  progress: number;
}

interface GalleryItem {
  icon: any;
  color: string;
}

interface ReelStat {
  label: string;
}

const avatarProfiles: AvatarProfile[] = [
  {
    src: "https://api.dicebear.com/7.x/avataaars/svg?seed=motion1&backgroundColor=1f2937",
    alt: "Portrait of a motion designer",
  },
  {
    src: "https://api.dicebear.com/7.x/avataaars/svg?seed=motion2&backgroundColor=1f2937",
    alt: "Portrait of a product strategist",
  },
  {
    src: "https://api.dicebear.com/7.x/avataaars/svg?seed=motion3&backgroundColor=1f2937",
    alt: "Portrait of a UX researcher",
  },
];

const keyMetrics: Metric[] = [
  {
    label: "Project satisfaction",
    value: "98%",
    caption: "Last quarter",
  },
  {
    label: "Delivery cadence",
    value: "2.4x",
    caption: "Faster",
  },
  {
    label: "Retention rate",
    value: "92%",
    caption: "After 6 months",
  },
];

const motionProcess: ProcessStep[] = [
  {
    label: "Ideate & storyboard",
    progress: 82,
  },
  {
    label: "Motion exploration",
    progress: 64,
  },
  {
    label: "Polish & delivery",
    progress: 91,
  },
];

const inspirationGallery: GalleryItem[] = [
  { icon: Wand2, color: "from-indigo-500/20 to-purple-500/20" },
  { icon: MonitorPlay, color: "from-emerald-500/20 to-teal-500/20" },
  { icon: Focus, color: "from-rose-500/20 to-orange-500/20" },
  { icon: Layers, color: "from-blue-500/20 to-cyan-500/20" },
];

const reelStats: ReelStat[] = [
  { label: "3:42 min" },
  { label: "4.2K views" },
  { label: "Dynamic timing curves" },
];

const sectionVariants: Variants = {
  hidden: { opacity: 0, y: 32 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, ease: "easeOut" },
  },
};

const cardVariants: Variants = {
  hidden: { opacity: 0, y: 32 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, ease: "easeOut" },
  },
};

export function BentoGridBlock() {
  return (
    <section className="relative w-full overflow-hidden bg-transparent">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute left-1/2 top-0 h-[520px] w-[520px] -translate-x-1/2 rounded-full bg-white/[0.02] blur-[140px]" />
        <div className="absolute bottom-0 right-0 h-[360px] w-[360px] rounded-full bg-emerald-500/[0.03] blur-[120px]" />
        <div className="absolute left-1/4 top-1/2 h-[400px] w-[400px] rounded-full bg-indigo-500/[0.02] blur-[150px]" />
      </div>

      <div className="relative mx-auto max-w-7xl px-4 py-8 md:px-6 md:py-16">
        <motion.header
          variants={sectionVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.2 }}
          className="flex flex-col items-center gap-4 text-center"
        >
          <Badge
            variant="outline"
            className="inline-flex items-center gap-2 rounded-full border-white/10 bg-black/40 px-4 py-1.5 text-xs uppercase tracking-[0.2em] text-white/70 backdrop-blur"
          >
            UI TripleD
            <span
              className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"
              aria-hidden="true"
            />
          </Badge>
          <h2 className="text-3xl font-semibold tracking-tight text-white md:text-4xl lg:text-5xl">
            Bento storytelling built for modern systems
          </h2>
          <p className="max-w-2xl text-base text-zinc-400 md:text-lg">
            Pair narrative, metrics, and cinematic visuals inside a responsive
            layout designed around Framer Motion micro-interactions and
            accessible navigation.
          </p>
        </motion.header>

        <motion.div
          className="mt-12 grid auto-rows-[minmax(200px,auto)] gap-4 sm:grid-cols-2 md:gap-6 lg:grid-cols-4"
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.2 }}
          variants={{
            hidden: { opacity: 0, y: 24 },
            visible: {
              opacity: 1,
              y: 0,
              transition: {
                duration: 0.6,
                ease: "easeOut",
                staggerChildren: 0.08,
                delayChildren: 0.12,
              },
            },
          }}
        >
          <motion.article
            variants={cardVariants}
            whileHover={{ y: -4 }}
            transition={{ duration: 0.2 }}
            className="group relative col-span-1 flex h-full flex-col justify-between overflow-hidden rounded-2xl border border-white/10 bg-zinc-950/50 p-6 backdrop-blur transition-all hover:border-white/20 hover:shadow-lg sm:col-span-2 lg:row-span-2 shadow-2xl"
            role="article"
            aria-label="Featured case study"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-white/[0.05] via-transparent to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
            <div className="relative flex h-full flex-col justify-between">
              <div className="space-y-4">
                <Badge
                  variant="secondary"
                  className="w-fit rounded-full border-white/10 bg-zinc-900/80 px-3 py-1 text-xs uppercase tracking-[0.2em] text-zinc-400"
                >
                  Featured case study
                </Badge>
                <h3 className="text-2xl font-semibold leading-tight text-white md:text-3xl">
                  Designing delightful product experiences
                </h3>
                <p className="text-sm text-zinc-400 md:text-base">
                  We choreograph micro-interactions and depth cues that elevate
                  usability across every product surface-without sacrificing
                  performance or accessibility.
                </p>
              </div>
              <div className="mt-8 flex items-center justify-between gap-4">
                <div
                  className="flex -space-x-3"
                  role="list"
                  aria-label="Project team avatars"
                >
                  {avatarProfiles.map((profile, i) => (
                    <div
                      key={i}
                      role="listitem"
                      className="relative h-11 w-11 overflow-hidden rounded-full border border-zinc-800 bg-zinc-900 transition-transform duration-300 group-hover:scale-[1.04]"
                    >
                      <Image
                        src={profile.src}
                        alt={profile.alt}
                        width={44}
                        height={44}
                        unoptimized
                        className="h-full w-full object-cover opacity-80"
                      />
                    </div>
                  ))}
                </div>
                <Button
                  variant="ghost"
                  className="group/cta gap-2 rounded-lg bg-zinc-900/70 px-4 py-2 text-sm text-white hover:bg-zinc-800"
                  aria-label="View the featured case study"
                >
                  View story
                  <ArrowUpRight className="h-4 w-4 text-emerald-500 transition-transform group-hover/cta:translate-x-1 group-hover/cta:-translate-y-1" />
                </Button>
              </div>
            </div>
          </motion.article>

          <motion.article
            variants={cardVariants}
            whileHover={{ y: -4 }}
            transition={{ duration: 0.2 }}
            className="group col-span-1 flex h-full flex-col rounded-2xl border border-white/10 bg-zinc-950/50 p-6 backdrop-blur transition-all hover:border-white/20 hover:shadow-lg sm:col-span-2 shadow-2xl"
            role="article"
            aria-label="Key performance metrics"
          >
            <div className="flex items-center justify-between">
              <Badge
                variant="secondary"
                className="w-fit rounded-full px-3 py-1 text-xs uppercase tracking-[0.2em] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20"
              >
                Performance
              </Badge>
              <motion.div
                animate={{ rotate: [0, -6, 0, 6, 0] }}
                transition={{
                  repeat: Infinity,
                  duration: 10,
                  ease: "easeInOut",
                }}
              >
                <Sparkles className="h-5 w-5 text-emerald-400" aria-hidden="true" />
              </motion.div>
            </div>
            <div className="mt-6 grid gap-4 sm:grid-cols-3 h-full">
              {keyMetrics.map((metric) => (
                <div key={metric.label} className="flex flex-col">
                  <p className="text-xs uppercase tracking-[0.18em] text-zinc-500 font-mono">
                    {metric.label}
                  </p>
                  <p className="mt-2 text-2xl font-semibold tracking-tight text-white md:text-3xl">
                    {metric.value}
                  </p>
                  <p className="mt-auto inline-flex items-center gap-2 px-2 py-1 text-xs font-semibold text-emerald-500 bg-emerald-500/10 rounded-full w-fit mt-3">
                    {metric.caption}
                  </p>
                </div>
              ))}
            </div>
          </motion.article>

          <motion.article
            variants={cardVariants}
            whileHover={{ y: -4 }}
            transition={{ duration: 0.2 }}
            className="group relative col-span-1 overflow-hidden rounded-2xl border border-white/10 bg-zinc-900/60 backdrop-blur hover:border-white/20 hover:shadow-lg sm:col-span-2 lg:row-span-3 shadow-2xl"
            role="article"
            aria-label="Behind the scenes studio imagery"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/10 via-emerald-500/5 to-transparent mix-blend-screen opacity-50 group-hover:opacity-100 transition-opacity duration-700" />
            <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 mix-blend-overlay" />
            
            <div className="absolute top-8 left-8 p-4 bg-white/5 rounded-2xl backdrop-blur-xl border border-white/10 shadow-2xl group-hover:scale-105 transition-transform duration-500">
               <Box className="w-12 h-12 text-indigo-400" strokeWidth={1.5} />
            </div>

            <div className="absolute right-0 bottom-1/3 w-64 h-64 bg-emerald-500/20 blur-[80px] rounded-full pointer-events-none group-hover:bg-emerald-400/30 transition-colors" />

            <div className="absolute inset-0 bg-gradient-to-t from-black via-zinc-950/60 to-transparent" />
            <div className="relative flex h-full flex-col justify-end space-y-4 p-6 md:p-8 z-10">
              <Badge
                variant="outline"
                className="w-fit rounded-full border-white/20 bg-black/60 px-3 py-1 text-xs uppercase tracking-[0.2em] text-zinc-300 backdrop-blur"
              >
                Behind the scenes
              </Badge>
              <h3 className="text-xl font-semibold tracking-tight text-white md:text-2xl">
                Immersive modular prototypes with cinematic glow
              </h3>
              <p className="max-w-sm text-sm text-zinc-400 md:text-base">
                Layered light cues and high-end geometric precision help teams experience the
                product as it will ship-well before the first line of production
                code.
              </p>
              <div className="flex flex-wrap gap-2 pt-2">
                {["Micro-interactions", "Depth cues", "Component API"].map(
                  (tag) => (
                    <span
                      key={tag}
                      className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.18em] text-zinc-400 font-mono"
                    >
                      {tag}
                    </span>
                  )
                )}
              </div>
            </div>
          </motion.article>

          <motion.article
            variants={cardVariants}
            whileHover={{ y: -4 }}
            transition={{ duration: 0.2 }}
            className="group col-span-1 flex h-full flex-col rounded-2xl border border-white/10 bg-zinc-950/50 p-6 backdrop-blur transition-all hover:border-white/20 hover:shadow-lg sm:col-span-2 lg:row-span-2 shadow-2xl"
            role="article"
            aria-label="Motion sprint process overview"
          >
            <div className="space-y-4">
              <Badge
                variant="outline"
                className="w-fit rounded-full border-indigo-500/30 bg-indigo-500/10 px-3 py-1 text-xs uppercase tracking-[0.2em] text-indigo-400"
              >
                Workflow sprint
              </Badge>
              <h3 className="text-xl font-semibold tracking-tight text-white md:text-2xl">
                From first sketch to polished prototype in seven days
              </h3>
              <p className="text-sm text-zinc-400 md:text-base">
                We compress discovery, exploration, and refinement into a
                focused week-long sprint.
              </p>
            </div>
            <div className="mt-6 space-y-4">
              {motionProcess.map((step, index) => (
                <div key={step.label} className="space-y-2">
                  <div className="flex items-center justify-between text-xs uppercase tracking-[0.18em] text-zinc-500 font-mono">
                    <span>{step.label}</span>
                    <span className="text-white" aria-label={`${step.progress}% complete`}>
                      {step.progress}%
                    </span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-white/5 border border-white/10">
                    <motion.div
                      initial={{ width: 0 }}
                      whileInView={{ width: `${step.progress}%` }}
                      viewport={{ once: true }}
                      transition={{
                        duration: 0.8,
                        ease: "easeOut",
                        delay: index * 0.1,
                      }}
                      className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-emerald-500"
                    />
                  </div>
                </div>
              ))}
            </div>
            <Button
              variant="ghost"
              className="mt-8 w-fit gap-2 px-0 text-sm text-emerald-400 hover:text-emerald-300 hover:bg-transparent"
              aria-label="Play sprint walkthrough video"
            >
              <PlayCircle className="h-4 w-4" aria-hidden="true" />
              Play walkthrough
            </Button>
          </motion.article>

          <motion.article
            variants={cardVariants}
            whileHover={{ y: -4 }}
            transition={{ duration: 0.2 }}
            className="group col-span-1 flex h-full flex-col overflow-hidden rounded-2xl border border-white/10 bg-zinc-950 p-0 backdrop-blur transition-all hover:border-white/20 hover:shadow-lg sm:col-span-2 shadow-2xl relative"
            role="article"
            aria-label="Motion showcase video"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-indigo-600/20 via-rose-600/10 to-transparent mix-blend-screen opacity-60 group-hover:opacity-100 transition-opacity duration-700" />
            <div className="relative h-full flex flex-col justify-end p-6 md:p-8 z-10 w-full min-h-[300px]">
                <div className="absolute top-8 right-8 w-16 h-16 bg-white/10 rounded-full flex items-center justify-center backdrop-blur-md border border-white/20 group-hover:scale-110 transition-transform">
                    <PlayCircle className="w-8 h-8 text-white fill-white/20" />
                </div>
                <div className="space-y-4">
                  <div className="flex items-center gap-3">
                    <Badge
                      variant="outline"
                      className="w-fit rounded-full border-white/20 bg-black/50 px-3 py-1 text-xs uppercase tracking-[0.2em] text-zinc-300"
                    >
                      Motion showcase
                    </Badge>
                  </div>
                  <h3 className="text-xl font-semibold tracking-tight text-white md:text-2xl mt-4">
                    Watch our latest architecture breakdown
                  </h3>
                  <p className="max-w-md text-sm text-zinc-400 md:text-base">
                    A three-minute deep dive into sovereign timing curves, coordinated
                    transitions, and how we translate component choreography.
                  </p>
                </div>
                <div className="flex flex-wrap items-center justify-between gap-3 pt-6 text-xs mt-auto">
                  <div className="flex flex-wrap gap-2">
                    {reelStats.map((stat) => (
                      <span
                        key={stat.label}
                        className="rounded-full bg-white/5 border border-white/10 px-3 py-1 uppercase tracking-[0.18em] text-white/50 font-mono"
                      >
                        {stat.label}
                      </span>
                    ))}
                  </div>
                </div>
            </div>
          </motion.article>

          <motion.article
            variants={cardVariants}
            whileHover={{ y: -4 }}
            transition={{ duration: 0.2 }}
            className="group col-span-1 flex h-full flex-col rounded-2xl border border-white/10 bg-zinc-950/50 p-6 backdrop-blur transition-all hover:border-white/20 hover:shadow-lg sm:col-span-2 shadow-2xl"
            role="article"
            aria-label="Visual research gallery"
          >
            <div className="space-y-3">
              <Badge
                variant="outline"
                className="w-fit rounded-full border-white/10 bg-zinc-900/50 px-3 py-1 text-xs uppercase tracking-[0.2em] text-zinc-400"
              >
                Visual research
              </Badge>
              <h3 className="text-lg font-semibold tracking-tight text-white md:text-xl">
                Capturing precision, shadow, and scale
              </h3>
              <p className="text-sm text-zinc-400 md:text-base">
                An archive of generative geometric primitives driving our sovereign language.
              </p>
            </div>
            <div className="mt-8 grid grid-cols-2 gap-3">
              {inspirationGallery.map((item, i) => (
                <div
                  key={i}
                  className={`relative aspect-[4/3] overflow-hidden rounded-xl border border-white/10 bg-gradient-to-br ${item.color} flex items-center justify-center`}
                >
                   <item.icon className="w-10 h-10 text-white/50 group-hover:text-white transition-colors duration-500 group-hover:scale-110" strokeWidth={1.5} />
                </div>
              ))}
            </div>
            <Button
              variant="ghost"
              className="mt-6 w-fit gap-2 px-0 text-sm text-indigo-400 hover:text-indigo-300 hover:bg-transparent"
              aria-label="Open the visual inspiration archive"
            >
              Open inspiration archive
              <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
            </Button>
          </motion.article>
        </motion.div>
      </div>
    </section>
  );
}
