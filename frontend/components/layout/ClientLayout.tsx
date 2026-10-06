'use client';

import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import { useStore } from '@/store';
import { Sidebar } from '@/components/layout/Sidebar';
import { TopBar } from '@/components/layout/TopBar';
import { LockScreen, PinPrompt } from '@/components/layout/LockScreen';
import { useSettingsStore } from '@/store/settings';

// SettingsDialog eagerly imports 8 settings sections into the global app-shell
// chunk loaded on every page. Load it off the initial-paint path instead.
const SettingsDialog = dynamic(
  () => import('@/components/settings/SettingsDialog').then((m) => m.SettingsDialog),
  { ssr: false }
);

export function ClientLayout({ children }: { children: React.ReactNode }) {
  const { settingsOpen, setSettingsOpen } = useStore();
  const [locked, setLocked] = useState(false);
  const [pinPrompt, setPinPrompt] = useState(false);
  const security = useSettingsStore((s) => s.settings?.security) as
    | Record<string, unknown>
    | undefined;
  const parental = useSettingsStore((s) => s.settings?.parental_controls) as
    | Record<string, unknown>
    | undefined;

  // Settings for lock/timeout/PIN decisions.
  useEffect(() => {
    const s = useSettingsStore.getState();
    if (!s.settings && !s.loading) void s.load().catch(() => undefined);
  }, []);

  // require_password → lock the app until verified (per tab, sessionStorage).
  // ponytail: async mimic — setState lives in the async callback, matching the
  // react-hooks/set-state-in-effect rule the same way the async settings load
  // in useChat does.
  useEffect(() => {
    let alive = true;
    (async () => {
      if (security?.require_password === true) {
        if (window.sessionStorage.getItem('sovereign.unlocked') !== '1') {
          if (alive) setLocked(true);
        } else {
          if (alive) setLocked(false);
          window.sessionStorage.removeItem('sovereign.unlocked');
        }
      } else {
        if (alive) setLocked(false);
        window.sessionStorage.removeItem('sovereign.unlocked');
      }
    })();
    return () => {
      alive = false;
    };
  }, [security?.require_password]);

  // session_timeout_minutes: lock after N idle minutes (0 = off).
  useEffect(() => {
    const mins = Number(security?.session_timeout_minutes ?? 0);
    if (!mins || mins <= 0 || locked) return;
    let timer: number;
    const reset = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        window.sessionStorage.removeItem('sovereign.unlocked');
        setLocked(true);
      }, mins * 60 * 1000);
    };
    const evs: (keyof WindowEventMap)[] = ['mousemove', 'keydown', 'click', 'scroll', 'touchstart'];
    evs.forEach((e) => window.addEventListener(e, reset, { passive: true }));
    reset();
    return () => {
      window.clearTimeout(timer);
      evs.forEach((e) => window.removeEventListener(e, reset));
    };
  }, [security?.session_timeout_minutes, locked]);

  // require_pin_for_settings → show PIN overlay while Settings tries to open.
  // ponytail: async mimic for the same lint rule (see require_password effect).
  useEffect(() => {
    let alive = true;
    (async () => {
      if (parental?.require_pin_for_settings !== true) {
        if (alive) setPinPrompt(false);
        return;
      }
      const alreadyOk = window.sessionStorage.getItem('sovereign.pin_ok') === '1';
      if (settingsOpen && !alreadyOk && alive) setPinPrompt(true);
    })();
    return () => {
      alive = false;
    };
  }, [settingsOpen, parental?.require_pin_for_settings]);

  const closePin = () => {
    setPinPrompt(false);
    // user cancelled — close the settings dialog too
    if (useStore.getState().settingsOpen) setSettingsOpen(false);
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Skip link: keyboard users jump past the sidebar/topbar to content */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:px-4 focus:py-2 focus:rounded-lg focus:bg-primary focus:text-primary-foreground focus:text-sm"
      >
        Skip to content
      </a>
      {locked ? (
        <LockScreen onUnlock={() => setLocked(false)} />
      ) : (
        <>
          <Sidebar />
          <div className="flex flex-col flex-1 overflow-hidden">
            <TopBar />
            <main id="main-content" className="flex-1 overflow-auto p-6">
              {children}
            </main>
          </div>
          <SettingsDialog
            open={Boolean(settingsOpen)}
            onOpenChange={(open) => setSettingsOpen(open)}
            initialSection={typeof settingsOpen === 'string' ? settingsOpen : undefined}
          />
        </>
      )}
      {pinPrompt && <PinPrompt onUnlock={() => setPinPrompt(false)} onCancel={closePin} />}
    </div>
  );
}
