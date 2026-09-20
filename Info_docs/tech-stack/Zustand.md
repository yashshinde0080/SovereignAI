---
tags: [frontend, state-management, react]
source: "[[Docs/Zustand.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# Zustand

Zustand manages client-side state in the SovereignAI Edge frontend, providing a small (~1 KB), fast, and scalable alternative to heavier state management libraries. It handles chat state (current conversation messages and streaming token buffer), UI state (loading indicators, panel visibility, theme preferences), model selection (currently selected model and its load status), and plugin configuration state.

Unlike Redux or MobX, Zustand requires no boilerplate, no provider components, and no action dispatchers -- stores are plain hooks that can be called from any component. TypeScript type inference works out of the box, making it a natural fit for the React + TypeScript frontend stack.

## Key Points

- ~1 KB bundle size with zero boilerplate and no provider wrappers
- Stores: chat state, UI state, model selection, plugin configuration
- TypeScript type inference is fully supported
- Direct hook-based API -- `const chats = useChatStore(state => state.chats)`
- Works alongside React 18+ hooks without additional abstractions

## Related
- [[React]]
- [[Technical Architecture]]
