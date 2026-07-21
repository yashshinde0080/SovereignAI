---
tags: [frontend, styling, css]
source: "[[Docs/Tailwind CSS.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# Tailwind CSS

Tailwind CSS provides the styling foundation for the SovereignAI Edge frontend, using a utility-first approach that enables rapid UI development without leaving the HTML. It handles responsive design for the chat interface across desktop and mobile, includes built-in dark mode support for reduced eye strain, and integrates with shadcn/ui components for consistent design patterns.

Tailwind's build-time CSS generation purges unused styles, keeping the production bundle minimal. The framework integrates with Vite via the PostCSS plugin and supports custom theme configuration to match SovereignAI Edge branding. The utility-first approach means that styling remains co-located with components rather than spread across separate stylesheet files.

## Key Points

- Utility-first CSS framework for rapid, component-co-located styling
- Built-in dark mode support for reduced eye strain in local LLM usage
- Responsive design adapts chat UI across desktop and mobile viewports
- Custom theme configuration for SovereignAI Edge branding
- PurgeCSS integration removes unused styles in production builds
- PostCSS plugin integrates with Vite build pipeline

## Related
- [[React]]
- [[Technical Architecture]]
- [[Vite]]
