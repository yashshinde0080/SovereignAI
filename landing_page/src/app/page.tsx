'use client';

import Navbar from '@/components/Navbar';
import ScrollSequence from '@/components/ScrollSequence';
import Footer from '@/components/Footer';

export default function Home() {
  return (
    <main id="main" style={{ position: 'relative', background: '#050505', minHeight: '100vh' }}>
      <Navbar />
      <ScrollSequence />
      <Footer />
    </main>
  );
}