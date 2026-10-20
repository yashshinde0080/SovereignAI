'use client';

import type { SettingsMap } from '@/types';
import { API_BASE } from '@/lib/apiBase';

/** Apply theme class to <html> instantly (light/dark/system). */
export function applyTheme(theme: unknown): void {
  if (typeof window === 'undefined') return;
  const root = document.documentElement;
  const mq = window.matchMedia('(prefers-color-scheme: dark)');
  const mode =
    theme === 'light' || theme === 'dark'
      ? theme
      : theme === 'system'
        ? mq.matches
          ? 'dark'
          : 'light'
        : null;
  if (!mode) return; // unknown value → leave as-is
  root.classList.toggle('dark', mode === 'dark');
}

/** font_size: base UI font scale via CSS var (clamped by schema 10–24). */
export function applyFontSize(size: unknown): void {
  if (typeof window === 'undefined') return;
  const n = Number(size);
  if (!Number.isFinite(n)) return;
  const px = Math.min(24, Math.max(10, Math.round(n)));
  document.documentElement.style.setProperty('--app-font-size', `${px}px`);
  window.localStorage.setItem('sovereign.font_size', String(px));
}

/** language: <html lang> attribute + localStorage cache for boot. */
export function applyLanguage(lang: unknown): void {
  if (typeof window === 'undefined') return;
  const v = String(lang || 'en');
  document.documentElement.lang = v;
  window.localStorage.setItem('sovereign.language', v);
}

export async function persistTheme(theme: string): Promise<void> {
  try {
    await fetch(`${API_BASE}/v1/settings/general`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ theme }),
    });
  } catch {
    // non-fatal
  }
}

/** Watch OS theme changes so "system" tracks the OS live. */
export function watchSystemTheme(): () => void {
  if (typeof window === 'undefined') return () => undefined;
  const mq = window.matchMedia('(prefers-color-scheme: dark)');
  const onChange = () => {
    const root = document.documentElement;
    if (!root.dataset.themeSetting || root.dataset.themeSetting === 'system') {
      applyTheme('system');
    }
  };
  mq.addEventListener('change', onChange);
  return () => mq.removeEventListener('change', onChange);
}

/**
 * Boot-time restore: theme (no flash) + font size + language.
 * localStorage first (instant), then backend reconcile (source of truth).
 */
export function bootTheme(defaultTheme = 'system'): void {
  if (typeof window === 'undefined') return;
  const saved = window.localStorage.getItem('sovereign.theme');
  const initial = saved || defaultTheme;
  document.documentElement.dataset.themeSetting = initial;
  applyTheme(initial);
  applyFontSize(window.localStorage.getItem('sovereign.font_size') ?? 14);
  applyLanguage(window.localStorage.getItem('sovereign.language') ?? 'en');

  fetch(`${API_BASE}/v1/settings/general`)
    .then((r) => (r.ok ? r.json() : null))
    .then((general: Record<string, unknown> | null) => {
      const backendTheme = (general?.theme as string) || 'system';
      // Trust backend unless nothing saved there and localStorage is empty.
      if (!saved && backendTheme) {
        window.localStorage.setItem('sovereign.theme', backendTheme);
      }
      const effective = saved || backendTheme;
      document.documentElement.dataset.themeSetting = effective;
      applyTheme(effective);
      applyFontSize(general?.font_size ?? 14);
      applyLanguage(general?.language ?? 'en');
    })
    .catch(() => undefined);
}

export type { SettingsMap };
