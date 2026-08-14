'use client';

import dynamic from 'next/dynamic';
import { useStore } from '@/store';
import { Sidebar } from '@/components/layout/Sidebar';
import { TopBar } from '@/components/layout/TopBar';

// SettingsDialog eagerly imports 8 settings sections into the global app-shell
// chunk loaded on every page. Load it off the initial-paint path instead.
const SettingsDialog = dynamic(
  () => import('@/components/settings/SettingsDialog').then((m) => m.SettingsDialog),
  { ssr: false }
);

export function ClientLayout({ children }: { children: React.ReactNode }) {
  const { settingsOpen, setSettingsOpen } = useStore();

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Skip link: keyboard users jump past the sidebar/topbar to content */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:px-4 focus:py-2 focus:rounded-lg focus:bg-primary focus:text-primary-foreground focus:text-sm"
      >
        Skip to content
      </a>
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar />
        <main id="main-content" className="flex-1 overflow-auto p-6">
          {children}
        </main>
      </div>
      <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
    </div>
  );
}
