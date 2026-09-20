import type { Metadata } from 'next';
import { Oxanium, Source_Code_Pro } from 'next/font/google';
import './globals.css';
import { ClientLayout } from '@/components/layout/ClientLayout';
import { Toaster } from '@/components/ui/toaster';

const oxanium = Oxanium({ subsets: ['latin'], variable: '--font-oxanium' });
const sourceCodePro = Source_Code_Pro({ subsets: ['latin'], variable: '--font-scm' });

export const metadata: Metadata = {
  title: 'SovereignAI Edge',
  description: 'Portable Offline AI Platform',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className={`${oxanium.variable} ${sourceCodePro.variable} font-sans`} suppressHydrationWarning>
        <ClientLayout>
          {children}
        </ClientLayout>
        <Toaster />
      </body>
    </html>
  );
}