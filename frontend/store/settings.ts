'use client';

import { create } from 'zustand';
import type { SettingsMap } from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

const DEBOUNCE_MS = 400;

interface SettingsStore {
  settings: SettingsMap | null;
  loading: boolean;
  error: string | null;
  /** Per-section in-flight PATCH trackers for rollback. */
  load: () => Promise<void>;
  updateSection: (section: string, data: Record<string, unknown>) => Promise<void>;
  /** Debounced save — coalesces rapid slider drags into one PUT. */
  saveSectionDebounced: (section: string, data: Record<string, unknown>) => void;
  resetAll: () => Promise<void>;
  flushPending: () => Promise<void>;
}

const timers: Record<string, ReturnType<typeof setTimeout>> = {};
const pending: Record<string, Record<string, unknown>> = {};

async function putSection(section: string, data: Record<string, unknown>) {
  const res = await fetch(`${API_BASE}/v1/settings/${section.replace(/_/g, '-')}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Save failed (${res.status})`);
  }
}

export const useSettingsStore = create<SettingsStore>((set, get) => ({
  settings: null,
  loading: false,
  error: null,

  load: async () => {
    set({ loading: true, error: null });
    try {
      const res = await fetch(`${API_BASE}/v1/settings`);
      if (!res.ok) throw new Error(`Failed to load settings (${res.status})`);
      const data = await res.json();
      set({ settings: data, loading: false });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e), loading: false });
    }
  },

  updateSection: async (section, data) => {
    // Optimistic
    const prev = get().settings;
    set((s) => ({ settings: { ...s.settings, [section]: data } }));
    try {
      await putSection(section, data);
    } catch (e) {
      // Rollback
      set({ settings: prev });
      throw e;
    }
  },

  saveSectionDebounced: (section, data) => {
    pending[section] = data;
    // Optimistic immediately
    set((s) => ({ settings: { ...s.settings, [section]: data } }));
    if (timers[section]) clearTimeout(timers[section]);
    timers[section] = setTimeout(async () => {
      const payload = pending[section];
      delete pending[section];
      const prev = get().settings;
      try {
        await putSection(section, payload);
      } catch {
        set({ settings: prev }); // rollback
      }
    }, DEBOUNCE_MS);
  },

  resetAll: async () => {
    const prev = get().settings;
    set({ settings: null });
    try {
      const res = await fetch(`${API_BASE}/v1/settings/reset`, { method: 'POST' });
      if (!res.ok) throw new Error('Reset failed');
      await get().load();
    } catch (e) {
      set({ settings: prev, error: e instanceof Error ? e.message : String(e) });
      throw e;
    }
  },

  flushPending: async () => {
    const jobs = Object.entries(pending);
    for (const [section, data] of jobs) {
      if (timers[section]) clearTimeout(timers[section]);
      delete timers[section];
      delete pending[section];
      await putSection(section, data).catch(() => undefined);
    }
  },
}));
