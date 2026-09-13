# SovereignAI Edge - Frontend

This directory contains the frontend application for SovereignAI Edge, a portable AI platform for running large language models locally on consumer hardware.

## Overview

- **Next.js 16 + React 19**: Modern React framework with App Router and Server Components
- **Static Export**: Optimized for Electron desktop wrapper via `next.config.ts` with `output: 'export'`
- **UI Library**: shadcn/ui (New York theme) with Tailwind CSS v4 (`@theme inline` CSS variables)
- **State Management**: Zustand 5 for global state
- **Features**:
  - Chat interface with model selection, parameter tuning, and streaming responses
  - System prompt and RAG context management
  - Model library browsing and management
  - Settings configuration (general, security, cloud providers)
  - Plugin marketplace and configuration
  - Benchmarking and performance metrics
  - Theme switching (light/dark) with oklch color tokens

## Key Directories

- `app/`: Next.js App Router components (page.tsx, layout.js, etc.)
- `components/`: Reusable UI components (shadcn/ui based)
- `lib/`: Utility functions, hooks, and API service wrappers
- `public/`: Static assets
- `styles/`: Global CSS (globals.css with Tailwind v4 `@theme inline`)
- `next.config.ts`: Configuration for static export and image optimization

## Development

- Node.js 18+ (npm only - no Yarn/PnPM)
- Dependencies locked via `frontend/package-lock.json`
- Dev server: `npm run dev` (from frontend/ directory)
- Build for Electron: `npm run build` (exports to `frontend/out/`)
- Lint: `npm run lint`
- Test: `node --test lib/maskedLm.test.ts` (example unit test)

## Integration

- Communicates with backend via REST/WebSocket at `http://127.0.0.1:8000/v1/*`
- In Electron: loads `app://` protocol serving `frontend/out/` in production, or `http://localhost:3000` in dev (with `USE_DEV_SERVER=true`)
- Designed to work offline-first with optional cloud API mode