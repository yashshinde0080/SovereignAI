# Landing Page — Issue Report

Audit with ponytail (over-engineering) + caveman (terse) lenses.

---

## 1. Dead Code — Hero.tsx Unused

`components/Hero.tsx` (200+ lines) imported nowhere. `page.tsx` renders only `Navbar` + `ScrollSequence`. Hero is dead weight.

**Fix:** Delete `Hero.tsx`.

---

## 2. ScrollSequence.tsx — 800+ Line Monolith

One file does: image preloader, canvas renderer, scroll→frame mapper, rAF lerp loop, resize handler, loading screen, content overlay, section opacity logic, frame counter, scroll indicator. Violates single responsibility.

**Fix:** Split into: `FramePreloader`, `CanvasRenderer`, `ContentOverlay`, `LoadingScreen`. Each <100 lines.

---

## 3. 240 Frame Preload — No Lazy Loading

`new Array(240)` all at once. Each JPEG ~1-2MB = ~300-500MB download before user sees anything. Loading screen makes it worse — user waits 30-60s.

**Fix:** Load first 30-40 frames, rest on-demand as user scrolls. Or replace 240 JPEGs with one MP4 + canvas.

---

## 4. 240+ React Re-Renders During Load

`setLoadProgress` called per-frame inside `loadFrame()` — 240 state updates during preload. Forces React to re-render the entire tree 240 times.

**Fix:** Batch progress updates (every 10 frames, or use ref + rAF throttle).

---

## 5. Scroll → setScrollProgress On Every Pixel

`onScroll` handler calls `setScrollProgress(Math.max(0, Math.min(1, -rect.top / scrollable)))` on every single scroll event — no throttle, no rAF sync. Jank on low-end devices.

**Fix:** Use rAF throttling or `useTransform` from framer-motion.

---

## 6. rename-frames: Two Implementations, Both Stale

- `rename-frames.js` (root) — script points to wrong dir `sovereignaiframes/` (doesn't exist), always says "Done! Renamed 240 frames" regardless of actual success.
- `src/app/api/rename-frames/route.ts` — GET endpoint that renames files (violates HTTP verb semantics, should be POST). Also runs against already-renamed files, so does nothing.

**Fix:** Delete both. Frames already renamed. If kept, one implementation only, via POST, point to correct dir, report actual count.

---

## 7. README.md Is Default create-next-app Boilerplate

Zero customization. Describes Geist font and Vercel deployment for a project that is neither.

**Fix:** Write real README: what SovereignAI Edge is, how to install, build, run.

---

## 8. Empty Scaffold Dirs — `hooks/`, `utils/`

Both directories exist with zero files. Premature scaffolding.

**Fix:** Delete both until something actually goes in them.

---

## 9. Hero Scroll Indicator + ScrollSequence Scroll Indicator = Duplicated

Hero.tsx has a scroll indicator (framer-motion). ScrollSequence also has one. Since Hero is dead code, only one exists at runtime — but still indicates the duplication pattern.

---

## 10. Package.json — Version Drift + Unused Dep

- `next: "14.1.0"` — AGENTS.md says "Next.js 16". Mismatch.
- `react: "^18.2.0"` — React 19 is current.
- `autoprefixer` in devDependencies but NOT in `postcss.config.mjs` — unused dep.

---

## 11. postcss.config.mjs Missing Autoprefixer

`autoprefixer` installed as devDep but postcss config only loads `tailwindcss`. Autoprefixer won't run.

**Fix:** Add `autoprefixer: {}` to postcss plugins.

---

## 12. tailwind.config.ts — Overly Broad Content Glob

`'**/*.{js,ts,jsx,tsx,mdx}'` as fallback — scans `node_modules`, `.next`, everything. Slows down build.

**Fix:** Remove the wildcard fallback. The two explicit paths cover the project.

---

## 13. globals.css — Tailwind Reset + Manual Reset Duplication

`* { margin: 0; padding: 0; box-sizing: border-box; }` — Tailwind's `@tailwind base` already applies `preflight` which does this.

**Fix:** Remove manual reset. Let Tailwind preflight handle it.

---

## 14. Double Vignette Overlay

ScrollSequence applies TWO overlays on the canvas (lines ~434-452):
1. Cinematic gradient overlay (top/bottom + left/right)
2. Extra dark scrim (`rgba(0,0,0,0.35)`)

The second layer is redundant — the cinematic gradient already darkens edges and center is ~`rgba(5,5,5,0.2)`.

---

## 15. Canvas DPR Handling Repeats Every Frame

`const dpr = window.devicePixelRatio || 1;` computed inside `drawFrame()` which runs on every rAF tick (60fps). DPR doesn't change between frames.

**Fix:** Compute DPR once in a resize handler, cache in ref.

---

## 16. No Tests

Zero test files. Not even a placeholder. `landing_page/` has no `__tests__` dir, no jest config.

---

## 17. Frame Counter Always Visible

Bottom-right "Frame 001 / 240" counter shows during the entire scroll experience. Distracting for users; only useful during development.

**Fix:** Remove or make debug-only via environment variable.

---

## 18. Rename Script Error Swallowing

`rename-frames.js` catches all rename errors and continues silently. If all 240 files fail, it still prints "Done! Renamed 240 frames." Misleading.

---

## Summary (Ponytail Ladder Applied)

| # | Issue | Type | Action |
|---|-------|------|--------|
| 1 | Hero.tsx dead code | YAGNI | Delete |
| 2 | ScrollSequence 800-line monolith | Over-engineering | Split |
| 3 | 240-frame preload | Performance | Lazy load |
| 4 | 240 React re-renders | Performance | Batch |
| 5 | No scroll throttle | Performance | rAF sync |
| 6 | Duplicate rename scripts | Dead code | Delete |
| 7 | Default README | Not customized | Write real one |
| 8 | Empty hooks/utils dirs | Premature scaffolding | Delete |
| 9 | Duplicate scroll indicators | Redundancy | Consolidate |
| 10 | Next 14.1 vs claimed 16 | Version drift | Sync |
| 11 | autoprefixer unused | Dead dep | Wire or remove |
| 12 | Wildcard Tailwind content glob | Slow build | Remove |
| 13 | Double CSS reset | Redundancy | Remove manual |
| 14 | Double vignette overlay | Visual redundancy | Remove second |
| 15 | Per-frame DPR calc | Inefficiency | Cache in ref |
| 16 | No tests | Missing | Add |
| 17 | Frame counter always on | Debug UI leftover | Hide in prod |
| 18 | Rename script lies about success | Bug | Fix reporting |

**Biggest wins:** Delete Hero.tsx + both rename scripts + empty dirs = 4 files gone, 0 feature loss. Lazy-load frames = 10x faster initial load.