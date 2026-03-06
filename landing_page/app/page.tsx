"use client";

import { ReactNode } from "react";
import { motion } from "framer-motion";
import FibonacciLanding from "@/components/fibonacci-layout";
import { CTAHeroBlock } from "@/components/uitripled/cta-hero-block-shadcnui";
import { StatsCounterBlock } from "@/components/uitripled/stats-counter-block-shadcnui";
import { AboutUsSection } from "@/components/uitripled/about-us-section-shadcnui";
import { BentoGridBlock } from "@/components/uitripled/bento-grid-block-shadcnui";
import { TimelineBlock } from "@/components/uitripled/timeline-block-shadcnui";
import CommunitySection from "@/components/content-6";
import { FAQAccordionBlock } from "@/components/uitripled/faq-accordion-block-shadcnui";
import { ContactFormSection } from "@/components/uitripled/contact-form-section-shadcnui";
import { FooterBlock } from "@/components/uitripled/footer-block-shadcnui";

function FadeIn({ children, delay = 0 }: { children: ReactNode, delay?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-100px" }}
      transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1], delay }}
      className="h-full w-full"
    >
      {children}
    </motion.div>
  );
}

function BlockContainer({ children, className = "" }: { children: ReactNode, className?: string }) {
  const baseClass = "h-full w-full bg-zinc-950/60 backdrop-blur-3xl rounded-[3rem] border border-white/5 overflow-hidden relative group hover:border-white/15 hover:shadow-[0_0_40px_rgba(255,255,255,0.03)] transition-all duration-700 shadow-2xl [&>section]:!py-12 md:[&>section]:!py-16 [&>section]:!px-8 md:[&>section]:!px-12 [&>section]:!bg-transparent [&_.mx-auto]:!mx-0 [&_.max-w-7xl]:!max-w-none [&_.max-w-5xl]:!max-w-none [&_.max-w-4xl]:!max-w-none [&_[data-slot='card']]:!bg-zinc-900/50 [&_[data-slot='card']]:!border-white/5 [&_.bg-card]:!bg-zinc-900/50 [&_.border-border]:!border-white/5";
  return (
    <div className={`${baseClass} ${className}`}>
      {/* Universal Ambient Block Inner Glow on Hover */}
      <div className="absolute inset-0 bg-gradient-to-b from-white/[0.03] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none z-0" />
      <div className="relative z-10 w-full h-full">
        {children}
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <div className="dark min-h-screen bg-[#030303] text-zinc-200 selection:bg-emerald-500/30 selection:text-white font-sans overflow-x-hidden relative">
      {/* Editorial Noise & Atmosphere */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[50%] h-[50%] rounded-full bg-zinc-600/5 blur-[150px]" />
        <div className="absolute top-1/2 right-1/4 w-[40%] h-[40%] rounded-full bg-zinc-800/10 blur-[150px]" />
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-[0.15] mix-blend-overlay" />
      </div>

      <main className="relative z-10 w-full max-w-[1920px] mx-auto px-4 md:px-6 py-6 flex flex-col gap-6 md:gap-8">
        
        {/* ROW 1: Custom Mathematical Hero Grid */}
        <FadeIn>
          <div className="w-full bg-[#030303] rounded-[3rem] border border-white/5 overflow-hidden shadow-[0_0_60px_rgba(0,0,0,0.8)] relative isolate">
            <FibonacciLanding />
          </div>
        </FadeIn>

        {/* 
          MACRO FIBONACCI GRID SYSTEM 
          We use a 13-column grid. The Fibonacci numbers are 1, 2, 3, 5, 8, 13
        */}

        {/* ROW 2: Fibonacci Split 8 : 5 */}
        <div className="grid grid-cols-1 xl:grid-cols-[repeat(13,minmax(0,1fr))] gap-6 md:gap-8">
          <div className="xl:col-[span_8_/_span_8]">
            <FadeIn delay={0.1}>
              <BlockContainer>
                <div className="absolute top-0 right-0 p-8 text-white/5 font-bold text-8xl pointer-events-none leading-none tracking-tighter mix-blend-overlay selection:bg-transparent">08</div>
                <CTAHeroBlock />
              </BlockContainer>
            </FadeIn>
          </div>
          <div className="xl:col-[span_5_/_span_5]">
             <FadeIn delay={0.2}>
              <BlockContainer className="flex flex-col justify-center">
                <div className="absolute top-0 right-0 p-8 text-white/5 font-bold text-7xl pointer-events-none leading-none tracking-tighter mix-blend-overlay selection:bg-transparent">05</div>
                <StatsCounterBlock />
              </BlockContainer>
            </FadeIn>
          </div>
        </div>

        {/* ROW 3: Fibonacci Split 5 : 8 */}
        <div className="grid grid-cols-1 xl:grid-cols-[repeat(13,minmax(0,1fr))] gap-6 md:gap-8">
          <div className="xl:col-[span_5_/_span_5]">
            <FadeIn delay={0.1}>
              <BlockContainer>
                <div className="absolute top-0 left-0 p-8 text-white/5 font-bold text-7xl pointer-events-none leading-none tracking-tighter mix-blend-overlay selection:bg-transparent">05</div>
                <AboutUsSection />
              </BlockContainer>
            </FadeIn>
          </div>
          <div className="xl:col-[span_8_/_span_8]">
            <FadeIn delay={0.2}>
              <BlockContainer>
                <div className="absolute top-0 right-0 p-8 text-white/5 font-bold text-8xl pointer-events-none leading-none tracking-tighter mix-blend-overlay selection:bg-transparent">08</div>
                <BentoGridBlock />
              </BlockContainer>
            </FadeIn>
          </div>
        </div>

        {/* ROW 4: Full span 13 */}
        <div className="grid grid-cols-1 xl:grid-cols-[repeat(13,minmax(0,1fr))] gap-6 md:gap-8">
            <div className="xl:col-[span_13_/_span_13]">
                <FadeIn delay={0.1}>
                    <BlockContainer>
                        <TimelineBlock />
                    </BlockContainer>
                </FadeIn>
            </div>
        </div>

        {/* ROW 5: Fibonacci Progression 3 : 2 : 8  (Sum = 13) */}
        <div className="grid grid-cols-1 xl:grid-cols-[repeat(13,minmax(0,1fr))] gap-6 md:gap-8">
            <div className="xl:col-[span_3_/_span_3]">
                <FadeIn delay={0.1}>
                    <BlockContainer className="group relative flex flex-col justify-between p-8 bg-gradient-to-br from-indigo-500/5 to-transparent overflow-hidden">
                        <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/10 blur-[80px] rounded-full mix-blend-screen pointer-events-none group-hover:bg-indigo-400/20 transition-colors duration-700" />
                        <div className="flex justify-between items-start relative z-10">
                            <div className="w-12 h-12 rounded-xl border border-indigo-500/30 bg-indigo-500/10 flex items-center justify-center text-indigo-400">
                                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>
                            </div>
                            <span className="text-indigo-500/40 font-mono text-xs font-bold">03</span>
                        </div>
                        <div className="relative z-10 mt-16">
                            <div className="flex items-baseline gap-2">
                                <span className="font-black text-6xl text-white tracking-tighter">842</span>
                                <span className="text-indigo-400 font-bold text-xl">K+</span>
                            </div>
                            <h3 className="text-zinc-400 font-mono text-sm tracking-widest uppercase mt-2">Active Global Nodes</h3>
                            <div className="mt-4 flex items-center gap-2">
                                <span className="relative flex h-3 w-3">
                                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                                  <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                                </span>
                                <span className="text-xs text-emerald-500 font-medium">Network Optimally Distributed</span>
                            </div>
                        </div>
                        {/* Decorative background number */}
                        <div className="absolute -bottom-10 -right-4 text-indigo-500/5 font-black text-[12rem] leading-none pointer-events-none select-none group-hover:text-indigo-500/10 transition-colors duration-700">3</div>
                    </BlockContainer>
                </FadeIn>
            </div>
            
            <div className="xl:col-[span_2_/_span_2]">
                <FadeIn delay={0.2}>
                    <BlockContainer className="group relative flex flex-col justify-between p-8 bg-gradient-to-tr from-rose-500/5 to-transparent overflow-hidden">
                        <div className="absolute bottom-0 left-0 w-48 h-48 bg-rose-500/10 blur-[60px] rounded-full mix-blend-screen pointer-events-none group-hover:bg-rose-400/20 transition-colors duration-700" />
                        <div className="flex justify-between items-start relative z-10">
                            <div className="w-12 h-12 rounded-xl border border-rose-500/30 bg-rose-500/10 flex items-center justify-center text-rose-400">
                                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
                            </div>
                            <span className="text-rose-500/40 font-mono text-xs font-bold">02</span>
                        </div>
                        <div className="relative z-10 mt-16 text-right">
                            <div className="flex items-baseline justify-end gap-1">
                                <span className="font-black text-6xl text-white tracking-tighter">.04</span>
                                <span className="text-rose-400 font-bold text-lg">ms</span>
                            </div>
                            <h3 className="text-zinc-400 font-mono text-sm tracking-widest uppercase mt-2">Avg. Latency</h3>
                        </div>
                        {/* Decorative background number */}
                        <div className="absolute -bottom-8 -left-2 text-rose-500/5 font-black text-[10rem] leading-none pointer-events-none select-none group-hover:text-rose-500/10 transition-colors duration-700">2</div>
                    </BlockContainer>
                </FadeIn>
            </div>

            <div className="xl:col-[span_8_/_span_8]">
                <FadeIn delay={0.3}>
                    <BlockContainer>
                        <div className="absolute top-0 right-0 p-8 text-white/5 font-bold text-8xl pointer-events-none leading-none tracking-tighter mix-blend-overlay selection:bg-transparent">08</div>
                        <CommunitySection />
                    </BlockContainer>
                </FadeIn>
            </div>
        </div>

        {/* ROW 6: Fibonacci Split 8 : 5 */}
        <div className="grid grid-cols-1 xl:grid-cols-[repeat(13,minmax(0,1fr))] gap-6 md:gap-8 lg:pb-10">
          <div className="xl:col-[span_8_/_span_8]">
            <FadeIn>
              <BlockContainer>
                <div className="absolute top-0 left-0 p-8 text-white/5 font-bold text-8xl pointer-events-none leading-none tracking-tighter mix-blend-overlay selection:bg-transparent">08</div>
                <FAQAccordionBlock />
              </BlockContainer>
            </FadeIn>
          </div>
          <div className="xl:col-[span_5_/_span_5]">
             <FadeIn delay={0.2}>
              <BlockContainer>
                <div className="absolute top-0 right-0 p-8 text-white/5 font-bold text-7xl pointer-events-none leading-none tracking-tighter mix-blend-overlay selection:bg-transparent">05</div>
                <ContactFormSection />
              </BlockContainer>
            </FadeIn>
          </div>
        </div>

        {/* FOOTER */}
        <FadeIn delay={0.1}>
            <div className="w-full bg-[#030303] rounded-[3rem] border border-white/5 overflow-hidden shadow-2xl">
              <FooterBlock />
            </div>
        </FadeIn>

      </main>
    </div>
  );
}
