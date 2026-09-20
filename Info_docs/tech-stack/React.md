---
tags: [frontend, ui, framework]
source: "[[Docs/React.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# React

React powers the frontend web interface of SovereignAI Edge, running inside the Electron desktop shell and also accessible as a standalone web UI. It renders the chat interface with real-time token streaming updates, manages UI state through Zustand, and uses a component library built with Tailwind CSS and shadcn/ui. React's virtual DOM provides efficient reconciliation for the large, rapidly-updating streaming chat logs that are characteristic of LLM interactions.

The frontend communicates with the backend via Axios for REST calls (model listing, status checks) and WebSocket for streaming token delivery. React 18+ hooks architecture organizes stateful logic into custom hooks, keeping components focused on rendering while Zustand stores handle global state like the current model selection and conversation history.

## Key Points

- React 18+ with hooks-based architecture for the UI layer
- Runs inside Electron shell or standalone browser
- Zustand for lightweight global state management (chat state, UI state, model selection)
- Tailwind CSS + shadcn/ui for the component library
- Next.js 16 (App Router) for the dev server and static-export production builds
- Real-time token rendering via WebSocket stream

## Related
- [[Zustand]]
- [[Tailwind CSS]]
- [[Technical Architecture]]
- [[Electron]]
