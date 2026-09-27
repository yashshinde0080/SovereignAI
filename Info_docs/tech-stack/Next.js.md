---
tags: [frontend, framework, nextjs]
source: "[[Docs/Next.js.md]]"
created: 2026-09-27
updated: 2026-09-27
---

# Next.js

Next.js 16 powers the SovereignAI Edge frontend with the App Router, React Server Components (RSC), and static export for Electron bundling. The dev server runs at `localhost:3000` with hot reload. Production builds output to `frontend/out/` via `output: 'export'` in `next.config.ts`, which Electron consumes via `app://` protocol (or `localhost:3000` in dev with `USE_DEV_SERVER=true`).

The frontend is a single-page chat interface with real-time token streaming via WebSocket (`/ws/metrics`) and REST (`/v1/*`). All paths are relative for USB portability. No API routes — all backend calls proxy to the FastAPI gateway at `127.0.0.1:8000`.

## Key Points

- Next.js 16 (App Router, RSC, TypeScript 5)
- Static export → `frontend/out/` (consumed by Electron as `extraResources`)
- Dev server: `npm run dev` at `localhost:3000`
- Build: `npm run build` → `frontend/out/`
- `trailingSlash: true`, `images.unoptimized` for static hosting
- Tailwind CSS v4 via `@tailwindcss/postcss` + `@theme inline` in `app/globals.css`
- shadcn/ui components in `components/ui/`, `cn()` utility in `lib/utils.ts`
- Zustand v5 for client state (`frontend/lib/store.ts`)
- No API routes — all backend via FastAPI on `127.0.0.1:8000`

## Config Highlights (`frontend/next.config.ts`)

```ts
const nextConfig = {
  output: 'export',
  trailingSlash: true,
  images: { unoptimized: true },
  // No API routes, no server-side rendering
}
```

## Related
- [[React]]
- [[Tailwind CSS]]
- [[Zustand]]
- [[Electron]]
- [[Technical Architecture]]