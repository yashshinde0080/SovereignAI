'use client';

import Navbar from '@/components/Navbar';
import ScrollSequence from '@/components/ScrollSequence';

export default function Home() {
  return (
    <main style={{ position: 'relative', background: '#050505', minHeight: '100vh' }}>
      <Navbar />
      <ScrollSequence />
    </main>
  );
}