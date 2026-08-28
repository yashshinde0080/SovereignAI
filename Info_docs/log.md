## [2026-08-28] feat | Chat UX polish + per-message model badge
- Backend: stream_response() now accepts model_name and emits it in the first SSE chunk's delta (backend/app/api/chat.py)
- Frontend: useChat captures model_name from stream delta + non-stream response, stores on Message.model (types/index.ts); ChatWindow/MessageList thread modelName prop and render small model label under assistant avatar
- ChatModule: listens for 'chat:send' CustomEvent so empty-state suggestion cards one-click send; moves Stop button inline next to Thinking toggle; compacts RAG doc chips and footer text
- MessageList: new empty state with 3 quick-start suggestion cards (Explain code / Brainstorm / Summarize); tighter message spacing; code blocks get smaller header with inline Copy/Copied label; loading dots switch bounce→pulse

## [2026-08-26] docs | Documentation updates + research references
- Documentation updates: added research references to algorithms-and-formulas.md and research-results.md; updated log.md with new entry; verified 112 tests passing