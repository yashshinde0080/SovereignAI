// Single source for the backend origin.
//
// The desktop app picks the port at startup (8000 can be taken, in which case
// it falls back to a free one), so it cannot be baked in at build time:
// electron/preload.js exposes the resolved address as window.sovereignRuntime.
// NEXT_PUBLIC_API_URL covers a dev build, and the default covers a plain
// `next dev` against a backend on its stock port.
type SovereignRuntime = { apiBase?: string; wsUrl?: string };

const runtime = (globalThis as { sovereignRuntime?: SovereignRuntime }).sovereignRuntime;
// Prefer the runtime-injected address, then env var for dev, then default.
export const API_BASE =
  runtime?.apiBase || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
// Derive WS_URL from the final API_BASE so it always matches the active port.
export const WS_URL = `$${API_BASE.replace(/^http/, 'ws')}/ws/metrics`;
