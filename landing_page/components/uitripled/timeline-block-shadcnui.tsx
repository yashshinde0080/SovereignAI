"use client";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { motion, useInView } from "framer-motion";
import { Calendar, CheckCircle2 } from "lucide-react";
import { useRef } from "react";

const timelineEvents = [
  {
    year: "2020",
    title: "Company Founded",
    description: "Started with a vision to transform how businesses operate digitally.",
    icon: CheckCircle2,
  },
  {
    year: "2021",
    title: "First 1,000 Customers",
    description: "Reached our first major milestone with customers across 20 countries.",
    icon: CheckCircle2,
  },
  {
    year: "2022",
    title: "Series A Funding",
    description: "Raised $10M to accelerate product development and expand our team.",
    icon: CheckCircle2,
  },
  {
    year: "2023",
    title: "Global Expansion",
    description: "Opened offices in 5 new countries and launched multilingual support.",
    icon: CheckCircle2,
  },
  {
    year: "2024",
    title: "AI Integration",
    description: "Launched AI-powered features to help businesses scale faster.",
    icon: CheckCircle2,
  },
];

export function TimelineBlock() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, amount: 0.2 });

  return (
    <section ref={ref} className="w-full bg-transparent px-4 py-8 md:py-12 relative">
      <div className="mx-auto max-w-5xl relative z-10">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: -20 }}
          transition={{ duration: 0.6 }}
          className="mb-10 text-center"
        >
          <Badge className="mb-4 inline-flex items-center gap-2 rounded-full border-white/10 bg-white/5 px-4 py-1.5 text-xs text-zinc-400 font-mono backdrop-blur" variant="outline">
            <Calendar className="h-3.5 w-3.5 text-emerald-500" />
            Our Journey
          </Badge>
          <h2 className="mb-3 text-3xl font-black tracking-tighter text-white md:text-5xl lg:text-6xl">
            The Story of Our Growth
          </h2>
          <p className="mx-auto max-w-2xl text-base text-zinc-400 md:text-lg">
            From a small startup to a global protocol trusted by thousands
          </p>
        </motion.div>

        {/* Timeline */}
        <div className="relative mt-8">
          {/* Vertical line shadow/glow */}
          <div className="absolute left-[31px] md:left-1/2 md:-translate-x-1/2 top-0 h-full w-[1px] bg-white/5 blur-[1px]" />
          
          {/* Vertical line */}
          <motion.div
            className="absolute left-[31px] top-0 h-full w-[2px] bg-gradient-to-b from-emerald-500 via-emerald-500/50 to-transparent md:left-1/2 md:-translate-x-1/2"
            initial={{ scaleY: 0 }}
            animate={isInView ? { scaleY: 1 } : { scaleY: 0 }}
            transition={{ duration: 1.5, ease: "easeOut" }}
            style={{ transformOrigin: "top" }}
          />

          <div className="flex flex-col gap-6 md:gap-8 relative z-10">
            {timelineEvents.map((event, index) => {
              const Icon = event.icon;
              const isEven = index % 2 === 0;

              return (
                <motion.div
                  key={event.year}
                  initial={{ opacity: 0, y: 20 }}
                  animate={
                    isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }
                  }
                  transition={{
                    delay: index * 0.15,
                    duration: 0.5,
                    ease: "easeOut",
                  }}
                  className={`relative flex items-center w-full justify-between ${
                    isEven ? "md:flex-row" : "md:flex-row-reverse"
                  }`}
                >
                  {/* Spacer for alternating layout */}
                  <div className="hidden w-[45%] md:block" />

                  {/* Timeline node */}
                  <div className="absolute left-[15px] flex h-8 w-8 items-center justify-center md:left-1/2 md:-translate-x-1/2 shrink-0">
                    <motion.div
                      className="flex h-8 w-8 items-center justify-center rounded-full border-4 border-zinc-950 bg-emerald-500 shrink-0 z-20"
                      initial={{ scale: 0 }}
                      animate={isInView ? { scale: 1 } : { scale: 0 }}
                      transition={{ delay: index * 0.15 + 0.3, type: "spring" }}
                    >
                      <Icon className="h-4 w-4 text-black" />
                    </motion.div>
                    <motion.div
                      className="absolute h-10 w-10 rounded-full bg-emerald-500/20 z-10"
                      animate={{ scale: [1, 1.5, 1], opacity: [0.5, 0, 0.5] }}
                      transition={{
                        duration: 2,
                        repeat: Infinity,
                        delay: index * 0.2,
                      }}
                    />
                  </div>

                  {/* Content card */}
                  <div className="w-[calc(100%-60px)] ml-[60px] md:ml-0 md:w-[45%] relative group">
                    <motion.div
                      whileHover={{ scale: 1.02, y: -2 }}
                      transition={{ duration: 0.2 }}
                    >
                      <Card className="relative overflow-hidden border border-white/10 bg-zinc-900/50 p-5 shadow-xl backdrop-blur-md">
                        <motion.div
                          className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100"
                          whileHover={{ opacity: 1 }}
                        />

                        <div className="relative z-10">
                          <Badge className="mb-3 bg-white/10 text-emerald-400 hover:bg-white/20 border-0" variant="secondary">
                            {event.year}
                          </Badge>
                          <h3 className="mb-2 text-lg font-bold text-white md:text-xl">
                            {event.title}
                          </h3>
                          <p className="text-sm text-zinc-400 md:text-base">
                            {event.description}
                          </p>
                        </div>
                      </Card>
                    </motion.div>
                  </div>
                  
                </motion.div>
              );
            })}
          </div>
        </div>

        {/* Future indicator */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
          transition={{ delay: timelineEvents.length * 0.15 + 0.5 }}
          className="mt-8 text-center"
        >
          <div className="inline-flex items-center gap-3 rounded-full border border-white/10 bg-zinc-900/50 px-5 py-2.5 backdrop-blur-sm">
            <motion.div
              animate={{ scale: [1, 1.2, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
              className="h-2 w-2 rounded-full bg-emerald-500"
            />
            <span className="text-sm font-medium text-zinc-300">
              And the timeline expands...
            </span>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
