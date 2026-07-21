# React

A JavaScript library for building user interfaces, developed by Meta (Facebook).

## Role in SovereignAI Edge

[[React]] powers the ==frontend web interface== of SovereignAI Edge. It runs inside the [[Electron]] shell and is also accessible as a standalone web UI:

- **Chat Interface:** Real-time token rendering via streaming updates
- **State Management:** Uses [[Zustand]] for lightweight local state
- **Component Library:** Built with [[Tailwind CSS]] and shadcn/ui components
- **Virtual DOM:** Efficient reconciliation for large streaming chat logs

## Technical Details

- **Version:** React 18+ with hooks-based architecture
- **Build Tool:** [[Vite]] for fast development and production bundling
- **Data Fetching:** Axios for REST calls, WebSocket for streaming

## See Also

- [[TRD]] — Technical requirements and stack details
- [[Electron]] — Desktop application shell
- [[Zustand]] — State management
- [[Tailwind CSS]] — Styling framework
- [[Vite]] — Build tool
