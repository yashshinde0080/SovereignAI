---
tags: [frontend, build-tool, bundler]
source: "[[Docs/Vite.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# Vite

Vite handles frontend development and production bundling for SovereignAI Edge. The development server provides Hot Module Replacement (HMR) for rapid UI iteration -- changes to React components, styles, or assets reflect in the browser or Electron window instantly without full page reloads. Production builds are optimized with code splitting, tree shaking, and asset minification.

Vite's plugin ecosystem enables seamless integration of Tailwind CSS via the PostCSS plugin. Its native ES module-based dev server serves modules on-demand rather than bundling everything upfront, resulting in near-instant server startup regardless of project size. For a local-first desktop application, this means the development feedback loop stays fast even as the frontend grows.

## Key Points

- HMR for instant feedback during UI development
- ES module-based dev server for near-instant startup
- Production builds with code splitting, tree shaking, and minification
- PostCSS plugin integration for Tailwind CSS
- Supports React and TypeScript out of the box

## Related
- [[React]]
- [[Technical Architecture]]
- [[Tailwind CSS]]
