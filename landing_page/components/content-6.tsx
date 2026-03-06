import Link from 'next/link';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { Users2, Sparkles } from 'lucide-react';

export default function CommunitySection() {
    const defaultUsers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
    
    return (
        <section className="relative flex flex-col items-center justify-center h-full min-h-[400px] p-8 overflow-hidden rounded-[2rem]">
            {/* Ambient Background */}
            <div className="absolute inset-0 bg-gradient-to-b from-transparent via-emerald-900/5 to-transparent pointer-events-none" />
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[300px] h-[300px] bg-emerald-500/10 blur-[100px] rounded-full pointer-events-none" />

            {/* Glowing Icon Header */}
            <div className="relative mb-8 z-10">
                <div className="px-4 py-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 tracking-[0.2em] font-mono text-xs font-bold uppercase inline-flex items-center gap-2 mb-6">
                    <Sparkles className="w-3.5 h-3.5" /> Core Contributors
                </div>
            </div>

            <div className="text-center relative z-10 z-20 mb-12">
                <h2 className="text-4xl md:text-5xl lg:text-6xl font-black tracking-tighter text-white mb-4">
                    The Hive <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-emerald-700">Mind.</span>
                </h2>
                <p className="text-zinc-400 max-w-lg mx-auto font-medium">
                    Thousands of autonomous agents and human developers building the decentralized sovereign core.
                </p>
            </div>

            {/* Dynamic Community Nodes Layout */}
            <div className="mx-auto flex max-w-2xl flex-wrap justify-center gap-3 md:gap-4 relative z-20">
                {defaultUsers.map((i, idx) => (
                    <motion.div
                        key={i}
                        initial={{ opacity: 0, scale: 0.5, y: 20 }}
                        whileInView={{ opacity: 1, scale: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ 
                            type: "spring", 
                            stiffness: 100, 
                            damping: 10,
                            delay: idx * 0.05 
                        }}
                    >
                        <Link 
                            href="#" 
                            className="group relative block w-14 h-14 md:w-16 md:h-16 rounded-full border border-white/10 bg-zinc-900/50 hover:bg-zinc-800 transition-all shadow-xl hover:shadow-[0_0_30px_rgba(16,185,129,0.3)] hover:-translate-y-2"
                        >
                            <Image 
                                alt={`Contributor ${i}`} 
                                src={`https://api.dicebear.com/7.x/avataaars/svg?seed=volunteer${i}&backgroundColor=18181b`} 
                                unoptimized
                                width={100} 
                                height={100} 
                                className="w-full h-full rounded-full object-cover p-1 opacity-70 group-hover:opacity-100 transition-opacity" 
                            />
                        </Link>
                    </motion.div>
                ))}
                
                {/* Plus Members Circle */}
                <motion.div
                    initial={{ opacity: 0, scale: 0.5 }}
                    whileInView={{ opacity: 1, scale: 1 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.8 }}
                >
                    <div className="w-14 h-14 md:w-16 md:h-16 rounded-full border border-emerald-500/30 bg-emerald-500/10 flex items-center justify-center text-emerald-400 font-bold font-mono text-sm hover:bg-emerald-500/20 transition-colors shadow-lg shadow-emerald-900/20">
                        9K+
                    </div>
                </motion.div>
            </div>
            
            <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-[#030303] to-transparent pointer-events-none z-10" />
        </section>
    );
}
