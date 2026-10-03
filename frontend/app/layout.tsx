import type { Metadata } from 'next';
import { Oxanium, Source_Code_Pro } from 'next/font/google';
import './globals.css';
import { ClientLayout } from '@/components/layout/ClientLayout';
import { Toaster } from '@/components/ui/toaster';
import { bootTheme } from '@/lib/themeBoot';

const oxanium = Oxanium({ subsets: ['latin'], variable: '--font-oxanium' });
const sourceCodePro = Source_Code_Pro({ subsets: ['latin'], variable: '--font-scm' });

export const metadata: Metadata = {
  title: 'SovereignAI Edge',
  description: 'Portable Offline AI Platform',
};

// Theme must apply before first paint — inline script, no layout jump.
// Reads localStorage cache; backend reconcile happens in bootTheme after load.
const THEME_BOOT = `(${bootTheme.toString()})();`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT }} />
      </head>
      <body className={`${oxanium.variable} ${sourceCodePro.variable} font-sans`} suppressHydrationWarning>
        <ClientLayout>
          {children}
        </ClientLayout>
        <Toaster />
      </body>
    </html>
  );
}