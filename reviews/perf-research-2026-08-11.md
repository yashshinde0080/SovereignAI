# Whole-App Performance Research — SovereignAI Edge

Date: 2026-08-11
Scope: Electron shell, React frontend, token streaming, FastAPI backend, build/bundle, app boot.
Method: read the actual code paths end-to-end (streaming, chat render, Electron boot, DB config, build config), then verify each proposed optimization against what exists. Findings below are grounded in `file:line` refs, not generic advice.

---

## TL;DR — ranked by actual bang for buck in THIS codebase

| # | Item | Reality check |
|---|------|---------------|
| 1 | Batch token updates in React | **Real, the biggest win.** `useChat.ts` calls `setMessages` per token. |
| 2 | Memoize chat message rows | **Real, pairs with #1.** No `React.memo` anywhere in the message tree; `ReactMarkdown` re-parses every message each tick. |
| 3 | Deserialize Electron boot | **Real, bigger than V8 snapshot.** `main.js` awaits backend before opening the window. |
| 4 | Window the chat tail (skip `react-window`) | **Conditional.** `react-window` fights variable-height markdown + framer-motion. Memo + batching first. |
| 5 | Dedup `/status` fetches + throttle metrics WS | **Real, small.** Multiple mounts call the same endpoints. |
| 6 | `next/dynamic` heavy deps | **Modest.** `recharts`/settings/plugins off the main bundle. |
| 7 | uvloop | **Not available on Windows.** Dep already correct. |
| 8 | gzip/brotli on API | **Skip.** Loopback + `file://` serving; compression is a net loss. |
| 9 | SQLite WAL / pooling | **Already fully done.** |
| 10 | `apscheduler` vacuum every 5 min | **Doesn't exist.** Don't add it. |
| 11 | V8 snapshot Electron | **Not supported on Windows.** |
| 12 | Splash flash / devtools | **Already done.** |

---

## 1. Electron / Desktop

### Already correct
- `electron/main.js:28` — `show: false` + `ready-to-show` (`main.js:44-46`). Splash flash is already killed. Nothing to do.
- `electron/main.js:35,40` — `openDevTools()` only runs when `isDev`. Prod never opens devtools. RAM win already in place.
- Single window, no full-UI boot problem — the app only ever creates one `BrowserWindow`.

### The real cold-start bottleneck is backend-first boot
`electron/main.js:211-216`:

```js
await startBackend();      // resolves only when uvicorn prints "Uvicorn running"
createWindow();
```

The window doesn't even start loading the React UI until the Python backend is up. On a cold start that's serial: Python venv import + FastAPI lifespan (DB init, vector store, hardware detect, model manager) *then* Chromium renders the frontend. The window should open first and render the static UI while the backend boots behind it — the UI can already draw the shell, and `/status` calls retry until the backend answers.

Lazy alternative that captures most of the win: keep the backend dependency, but fire `createWindow()` immediately and let the frontend's existing retry/WS-reconnect handle a briefly-unreachable backend. `metricsWs` already auto-reconnects every 3s (`frontend/lib/websocket.ts:32-35`).

### V8 snapshot — not viable on this target
The user's #3 item (V8 snapshot for faster cold start) does not apply: Electron's `v8SnapshotFile` build option is **macOS/Linux only**. This project targets win32 (`electron/package.json:47-50`, `nsis`). On Windows the cold-start wins are: parallelize backend boot (above), and trim what's loaded before first paint. Do not chase V8 snapshots here.

---

## 2. React frontend — the real problem, confirmed

### The streaming hot path: `frontend/hooks/useChat.ts`
`useChat.ts:254-257` calls `patchLastMessage` → `setMessages` **once per token**:

```ts
const reasoningToken = chunk.choices?.[0]?.delta?.reasoning || '';
const token = chunk.choices?.[0]?.delta?.content || '';
if (reasoningToken) assistantReasoning += reasoningToken;
if (reasoningToken || token) {
  if (token) assistantContent += token;
  patchLastMessage({ content: assistantContent, reasoning: assistantReasoning || undefined });
}
```

Each `setMessages` is a separate microtask off `reader.read()` — React does NOT batch them. Each one:

1. Rebuilds the whole array (`[...prev]`, `useChat.ts:194`).
2. Re-renders `MessageList` — **not memoized** (`frontend/components/chat/MessageList.tsx:147`).
3. Re-renders **every** message row inside `AnimatePresence` (`MessageList.tsx:189-323`), each a `motion.div`.
4. Re-runs `ReactMarkdown` on **every** message's content (`MessageList.tsx:265-279`) — for N messages that's N markdown parses per token tick. `react-markdown` re-parses from scratch; it is not memoized per message.

At ~20-40 tok/s this is the jank: a full O(N) markdown re-parse + DOM diff every ~30ms while streaming.

### Fix #1 — batch setState to one flush per animation frame
Accumulate into refs, flush at most once per frame. The streaming loop keeps appending to refs; a single rAF (or 50ms interval) callback commits to state:

```ts
const contentRef = useRef('');      // token accumulation, not state
const reasoningRef = useRef('');
const flushRef = useRef<number | null>(null);

const scheduleFlush = () => {
  if (flushRef.current !== null) return;         // one flush per frame
  flushRef.current = requestAnimationFrame(() => {
    flushRef.current = null;
    patchLastMessage({ content: contentRef.current, reasoning: reasoningRef.current || undefined });
  });
};
// in the token loop: contentRef.current += token; scheduleFlush();
// on done: cancel pending rAF, final patch.
```

The `useEffect` in `ChatWindow.tsx:32-41` that auto-scrolls on every `messages` change gets the same benefit automatically (fewer state commits = fewer forced scrollTop layout writes).

### Fix #2 — memoize the message tree
- `React.memo` the per-message row (extract the `motion.div` map body into a `MessageItem` component; pass `message` + stable callbacks).
- Memoize `CodeBlock`, `ThinkingBlock`, `CopyMessageButton`.
- Wrap `ReactMarkdown` per message so a completed message never re-parses: since rows are memoized and the array identity only changes for the tail, completed messages stop re-rendering entirely.
- Replace `key={index}` (`MessageList.tsx:192`) with a stable message id — index keys churn on edit/regenerate.

### Fix #3 — window the tail, not react-window
`react-window` (fixed row height) is a poor fit here: messages are variable-height markdown wrapped in framer-motion. The lazy correct version: while streaming, the only row that changes is the last one. With fixes #1+#2 the streaming row re-renders once per frame and everything else is memoized — DOM cost is already O(tail), not O(N). Only if conversations grow to hundreds of messages with visible scroll cost should you cap rendered history (render last ~100 + the streaming tail, full render on stream end). `react-window` is not the tool for this renderer.

---

## 3. Streaming / output

### Already correct
- SSE (`text/event-stream`, `backend/app/api/chat.py:126-130`), frontend streams via `getReader()` (`useChat.ts:180-264`). The "you already do" is accurate — no full-response wait anywhere.

### Server-side frame batching (cheap, optional)
`chat.py:220-245` yields one JSON-encoded SSE frame **per engine token**. Each frame is a full `StreamChunk` serialization. Accumulating ~5 tokens or ~50ms of tokens before each `yield` cuts frame count and JSON overhead ~10-20x. Small change in `stream_response`, low risk, modest win. Not required once the frontend batches — the per-token frames are small and localhost is fast.

### Backpressure
The server does not buffer if the client lags; `generate_stream` just keeps producing. For a single local client this is fine — the client's `reader.read()` paces the loop naturally (the stream is pull-based). No server-side flood risk through the SSE path. The **metrics WebSocket** is a different story:

`frontend/lib/websocket.ts` + `frontend/hooks/useMetrics.ts:76-89` push **every** metrics tick into `history` (capped 60) and call `setMetrics` + `setHistory` per message, while TopBar (global, `TopBar.tsx:11`) and Console and System pages each mount `useMetrics()`. Throttle history appends to ~1/s (that's the display granularity anyway) and gate `setMetrics` to a rAF/interval. Small, real win during inference when the WS is busiest.

---

## 4. FastAPI backend

### uvloop — not available on Windows
`requirements.txt:2` already pins `uvicorn[standard]==0.27.0`. `[standard]` pulls uvloop **on Unix only** — uvloop does not build on Windows, so uvicorn silently falls back to the asyncio loop. The proposed "free win" doesn't exist on this target (win32). No change needed; the dependency is already correct.

### gzip/brotli — skip
The frontend is served over Electron's `app://` protocol via `net.fetch(pathToFileURL(...))` (`electron/main.js:175-209`) — a `file://` fetch, **not HTTP**. API responses travel over `127.0.0.1` loopback and are tiny JSON. Compression costs CPU for zero transfer savings. If a future web deployment serves the frontend over HTTP, add it then. Not now.

### SQLite — already fully done
`backend/app/database/connection.py:57-72` already implements everything proposed:
- `PRAGMA journal_mode = WAL` (line 60)
- `busy_timeout` 5000 (line 51)
- `cache_size` 64MB (line 63)
- `synchronous = NORMAL` (line 66)
- `temp_store = MEMORY` (line 69)
- `mmap_size` 256MB (line 72)
- thread-local connection pool (lines 34-41)
- `checkpoint()`/`backup()` with WAL truncate (`manager.py:123-133`)

### The "apscheduler vacuum every 5 min" does not exist
`manager.py:117-121` defines `vacuum()` but **nothing calls it** — there is no scheduler in the codebase (`apscheduler` is not a dependency; grep across `backend/` returns only the method definition). The user's assumption was wrong, and that's fine: for a single-user edge app, WAL mode + a checkpoint on shutdown (`manager.py:143`) keeps the DB healthy. A periodic `VACUUM` is unnecessary, and if one is ever added it must run in a thread — `VACUUM` blocks the main loop. Recommend: don't add it.

---

## 5. Build / bundle

### The stack is Next.js static export, not Vite
The "Vite already fast / Tailwind v3 purge" framing doesn't match the code. This is **Next.js 16 with `output: 'export'`** (`frontend/next.config.ts:1-8`), **Tailwind v4** (`frontend/package.json:35,40`). `next build` emits static HTML into `frontend/out`, which Electron packages as `extraResources` (`electron/package.json:42-45`). There is no Vite, no server, no HTTP layer in production.

Implications:
- **Code splitting** — routes are already separate static pages; the app-shell JS is shared. The heavy page-only deps worth `next/dynamic`-ing (client-side lazy): `recharts` (`benchmark` page only, `frontend/package.json:25`), the settings dialog, the plugins page. `react-markdown` is on the chat critical path, so it stays.
- **Bundle analyzer** — the Next.js equivalent of `vite-bundle-visualizer` is `@next/bundle-analyzer`, not the Vite tool.
- **Source maps** — Next static export does not emit production source maps by default (`productionSourceMaps` is off); `frontend/out` ships minified. Already correct.

---

## 6. App boot / data fetching

### Duplicated `/status` fetches
- `useMetrics` (`useMetrics.ts:25-42`) fetches `/v1/system/status` on mount and is mounted from **three** places: global `TopBar` (`TopBar.tsx:11`), `system/page.tsx:16`, `console/page.tsx`. The global TopBar mount already covers the app; the page-level mounts re-fetch redundantly and each opens its own metrics WebSocket.
- `HomePage` (`frontend/app/page.tsx:19-39`) fetches `/status` + `/hardware` + `/recommendations` on mount on top of that.

The live source of truth is the metrics WebSocket, which already pushes model state (`useMetrics.ts:50-73`). Recommendation: fetch `/status` once into the store, derive everywhere; drop the per-page `useMetrics()` remounts or make them store-reads. This is a **React re-render/reconnect dedup**, not a network problem — on loopback every fetch is sub-millisecond, so the "cache `/status` client-side, don't refetch every mount" advice from SaaS-land mostly collapses to "stop mounting the same hook three times."

### Model list caching / prefetch — marginal
`listModels` reads a SQLite table on loopback; it's already fast. The prefetch-while-typing pattern is aimed at a network app. Not worth the machinery here. The honest answer: don't cargo-cult SaaS caching onto a localhost app; the real costs are render batching (#2) and WS/metrics dedup (#5), not round-trips.

---

## Recommended order of work

1. **`useChat.ts` rAF-batched flush + `MessageList` memoization** — this is the perceived speed of the whole product while streaming (the dominant interaction). ~1 file, the streaming path only.
2. **`electron/main.js` — open window before backend resolves** — biggest cold-start win available on Windows (V8 snapshot is unavailable).
3. **Metrics WS throttle + `/status` dedup** — small, contained, smooths the System/Console pages during inference.
4. **Server-side SSE frame batching in `stream_response`** — optional polish once the frontend batches.
5. **`next/dynamic` for `recharts`/settings/plugins** — modest initial-JS trim when bundle size is measured (run `@next/bundle-analyzer` first, don't guess).

## Explicitly not doing (with reasons)
- **uvloop** — not on Windows; dep already correct.
- **gzip/brotli** — loopback + `file://`; net loss.
- **V8 snapshot** — macOS/Linux only; target is win32.
- **`react-window`** — fights variable-height markdown + framer-motion; memo + batching covers the tail cost.
- **Periodic vacuum** — doesn't exist, WAL + shutdown checkpoint suffices; don't add a main-loop blocker.
- **Splash/devtools changes** — already done.

## Implementation status (2026-08-11)

**Done:**
- **Frontend batching** — `frontend/hooks/useChat.ts`: rAF-batched token flush (one `setMessages` per animation frame, not per token; `finally` cancels a pending flush so a mid-stream error can't clobber the error bubble). Action callbacks (`sendMessage`/`editAndResend`/`regenerate`) made stable via `messagesRef`.
- **Message memoization** — `frontend/components/chat/MessageList.tsx`: message row extracted into `React.memo`'d `MessageItem`; completed messages stop re-rendering and stop re-parsing `ReactMarkdown`. `frontend/components/task/ChatModule.tsx`: `onEditMessage`/`onRegenerate` are now `useCallback`'d (inline arrows would have defeated the memo).
- **Electron boot** — `electron/main.js`: window opens before the backend resolves; backend boots in parallel. Frontend's `/status` retry + `metricsWs` reconnect absorb the briefly-unreachable backend.
- **Backend SSE frame batching** — `backend/app/api/chat.py`: `stream_response` batches ~96 chars of tokens per SSE frame (was one frame per engine token), cutting frame count + JSON serialization ~10x while keeping deltas in order. Guarded by `backend/tests/test_stream_batch.py` (batching collapses tokens, reconstruction is lossless, finish frame trails content).

**Verified:** `tsc --noEmit` clean (frontend), `node --check` clean (Electron), 28 pytest tests pass (3 new + 25 existing).

**Done (follow-up):** `frontend/components/layout/ClientLayout.tsx` — `SettingsDialog` is now `next/dynamic`'d (`ssr: false`), pulling its 8 settings sections out of the global app-shell chunk. It's the only page-independent heavy import left; everything else is already route-split.

**Measured and rejected (do not build):**
- **Metrics WS throttle** — the backend pushes ~1/s (`backend/app/websocket/metrics.py:27-28`: 0.1s sample + 0.9s sleep). A "throttle history to 1/s" would be dead code.
- **`/status` dedup** — the redundant mounts (`useMetrics` in global `TopBar` + `system/page`) each add one sub-millisecond loopback fetch. Not worth hook restructuring; the metrics WS is already a shared singleton.
- **`next/dynamic` for `recharts`** — recharts is imported only by `ResourceChart` → only `system/page.tsx`; Next's route splitting already keeps it out of the chat/home initial load.
- **Chat-tail windowing** — still conditional; only if conversations grow past hundreds of messages with visible scroll cost. No evidence yet.
