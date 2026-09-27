---
tags: [frontend, styling, css]
source: "[[Docs/Tailwind CSS.md]]"
created: 2026-07-21
updated: 2026-09-27
---

# Tailwind CSS

Tailwind CSS v4 provides the styling foundation for the SovereignAI Edge frontend, using a utility-first approach that enables rapid UI development without leaving the HTML. It handles responsive design for the chat interface across desktop and mobile, includes built-in dark mode support for reduced eye strain, and integrates with shadcn/ui components for consistent design patterns.

Tailwind's build-time CSS generation purges unused styles, keeping the production bundle minimal. The framework integrates with Next.js via the `@tailwindcss/postcss` plugin and uses the new `@theme inline` CSS-variable pattern in `app/globals.css` (oklch tokens, `--brand #3C3489`, `--brand-accent #1D9E75`). The legacy `tailwind.config.js` (v3) remains but is not the authoritative config — `@theme inline` is the v4 path.

## Key Points

- Tailwind CSS v4 with `@theme inline` CSS-variable architecture
- Utility-first CSS framework for rapid, component-co-located styling
- Built-in dark mode support for reduced eye strain in local LLM usage
- Responsive design adapts chat UI across desktop and mobile viewports
- Custom theme configuration for SovereignAI Edge branding (oklch tokens)
- PurgeCSS integration removes unused styles in production builds
- PostCSS plugin (`@tailwindcss/postcss`) integrates with the Next.js 16 build pipeline
- shadcn/ui (new-york style, lucide icons, neutral base) via `components.json`

## Related
- [[React]]
- [[Next.js]]
- [[Technical Architecture]]