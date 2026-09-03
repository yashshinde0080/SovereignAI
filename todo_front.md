# Online Mode — Frontend, Electron & CLI Plan

**Status:** Planning
**Branch:** main
**Date:** 2026-09-03
**Depends on:** Backend cloud API from `TODOS.md` (§3) — this plan consumes `GET/POST/PUT/DELETE /v1/cloud/*`, cloud models via `/v1/models/*` with `mode=cloud`, and `/v1/chat/mode/switch?mode=cloud`.

**Scope:** Client-side work only. Three surfaces: React web (Next.js static export), Electron wrapper, Python CLI. All three talk to the same FastAPI gateway — nothing talks to providers directly.

---

## 1. Key Design Decisions (lazy by design)

1. **Electron needs ~zero code changes.** It's a thin wrapper (spawns uvicorn, serves `frontend/out`). Outbound provider calls are made by the backend, the renderer only talks to `127.0.0.1:8000` as it already does. The only Electron task is a QA pass in the packaged app.
2. **No new store slice.** `executionMode` in the Zustand store already exists — just widen its type union to include `"cloud"`. Provider/model state lives in a `useCloudProviders` hook mirroring `useModels` (existing pattern). The active cloud model is already tracked by `systemStatus.current_mode` + `currentModel`.
3. **`ModeSwitcher` stays untouched.** "cloud" is not a standalone mode you switch into — it's a consequence of loading a cloud model (same as loading a local model today). Loading `openai/gpt-4o` with `mode=cloud` sets the mode; the switcher keeps offering `fullram / layerstream / auto`.
4. **Cloud models are listed separately from local models.** `ModelTable`'s `Model` type is disk-centric (`size_gb`, `quant`, `downloaded`). Cloud models get their own compact list component fed by `/v1/cloud/models` — no surgery on the existing table.
5. **Onboarding wizard is cut.** First-run "connect your first API key" flow is deferred. An empty-state hint in the Cloud settings panel ("Add a provider to use online models") covers it.

---

## 2. Frontend Changes (Next.js static export)

### 2.1 Types — `frontend/types/index.ts`
```ts
export interface CloudProvider {
  id: string;
  name: string;
  provider_type: "openai" | "anthropic" | "google" | "mistral" | "custom";
  base_url?: string;          // null/absent for built-in providers
  api_key_masked?: string;    // "sk-…xxxx" — backend never returns the raw key
  is_enabled: boolean;
  rate_limit_rpm: number;
}

export interface CloudModel {
  id: string;                 // "<provider_id>/<model_id>", e.g. "openai/gpt-4o"
  name: string;
  provider_id: string;
  provider_type: string;
  context_window?: number;
  supports_streaming: boolean;
}
```

### 2.2 API client — `frontend/lib/api.ts`
Add methods to the existing `ApiClient` (mirror the `SettingsMap`/agents style):
```ts
listCloudProviders(): Promise<{ providers: CloudProvider[] }>          // GET  /v1/cloud/providers
addCloudProvider(cfg: { name; provider_type; api_key; base_url? }): Promise<CloudProvider>
updateCloudProvider(id, patch): Promise<CloudProvider>                 // PUT  /v1/cloud/providers/{id}
deleteCloudProvider(id): Promise<void>                                 // DELETE
testCloudProvider(id): Promise<{ ok: boolean; message?: string }>      // POST /v1/cloud/test/{id}
listCloudModels(): Promise<{ models: CloudModel[] }>                   // GET  /v1/cloud/models
refreshCloudModels(): Promise<{ models: CloudModel[] }>                // POST /v1/cloud/models/refresh
```

### 2.3 Store — `frontend/store/index.ts`
- Widen `executionMode` union: `"fullram" | "layerstream" | "auto" | "cloud"`.
- No new fields (see decision 2).

### 2.4 Settings — `frontend/components/settings/`
New file: **`CloudProvidersSettings.tsx`** (mirror `AgentSettings.tsx` pattern — self-contained CRUD via `api.*`, no `onSave` plumbing):
- List providers (name, type badge, masked key, enabled toggle, delete with confirm).
- "Add provider" inline form: type dropdown → API key input + optional base URL (shown for `custom`), provider name auto-filled from type.
- "Test" button per provider → `testCloudProvider`, show toast result.
- Empty state: "No cloud providers. Add an API key to use online models."

Edit **`SettingsDialog.tsx`**:
- Add `"cloud"` to the `Section` union, `{ key: "cloud", label: "Cloud / Online", icon: Cloud }` to the `sections` array, and a render branch `<CloudProvidersSettings />`.

### 2.5 Models page — cloud model list
New file: **`frontend/components/models/CloudModelList.tsx`** (consumed on the models page alongside `ModelTable`):
- Loads `listCloudModels()` on mount + after provider changes.
- Rows: model name, provider badge (`Cloud` icon), context window.
- Load button → `api.loadModel(model.id, "cloud")` (existing endpoint, backend resolves provider from the `provider_id/model_id` string).
- If no providers configured: one-line hint + link that opens the Settings dialog on the Cloud tab.

Edit the models page + **`frontend/components/models/ModelControlPanel.tsx`**:
- "Execution Mode" stat already renders `executionMode` — works once the union widens; show `CLOUD` naturally.
- When `executionMode === "cloud"`, swap the RAM "Power Distribution" bar for a static "Remote inference — no local RAM used" line (small conditional, skip if not trivial).

### 2.6 Chat UI — `frontend/components/chat/ChatWindow.tsx`
- When `systemStatus.current_mode === "cloud"`: show an indicator near the model label, e.g. "Online · gpt-4o via OpenAI". The streaming code path is untouched — backend re-emits provider SSE in the same format.

### 2.7 `frontend/hooks/useModels.ts`
- `setExecutionMode(current.mode as ...)` cast: widen the type param to include `"cloud"` so loading a cloud model doesn't lie about the mode.

---

## 3. Electron Changes

**None required.** Verification pass only:
- [ ] Packaged build (`npm run build:win` or `:linux`) — Cloud settings tab renders, provider add/test works, chat streams from a cloud model.
- [ ] No CSP changes — renderer only fetches `http://127.0.0.1:8000`; outbound HTTPS is backend-side.

Skipped: any cloud state in `preload.js`/`main.js`, tray/menu additions. Add when there's a concrete desktop-only feature (e.g., keychain storage of API keys — then `safeStorage` in `main.js` becomes relevant; not now).

---

## 4. CLI Changes — `backend/app/cli/main.py`

### 4.1 New `cloud` subcommand group (typer sub-app)
```bash
sovereign cloud add    --name "OpenAI" --type openai --key "sk-..." [--base-url ...]
sovereign cloud list                      # masked keys, enabled state
sovereign cloud remove <id>               # --force/-f to skip confirm
sovereign cloud test <id>                 # prints ok/failure message
sovereign cloud models [--provider <id>]  # tabulated model list
```
All hit the same `/v1/cloud/*` endpoints via the existing `httpx.AsyncClient` pattern (same `_api_base()` origin). `rich.Table` for list/models output.

### 4.2 Wire cloud into existing commands
- `_switch_mode()`: allow `"cloud"` in the valid-modes check (needed if user runs `/mode cloud` after loading a cloud model; harmless otherwise).
- `run` / `chat`: `--mode` already free-form → `sovereign run openai/gpt-4o --mode cloud` works with no change; document it in `help`.
- `help` table: add `cloud` row.
- `list`: leave local-only. `sovereign cloud models` is the online equivalent — don't clutter the local list.

---

## 5. Implementation Phases

### Phase 1: Frontend plumbing (0.5 day)
- [ ] Types: `CloudProvider`, `CloudModel` in `frontend/types/index.ts`
- [ ] `api.ts`: 7 cloud methods
- [ ] Store: widen `executionMode` union
- [ ] `useModels.ts` cast widened

### Phase 2: Settings UI (0.5–1 day)
- [ ] `CloudProvidersSettings.tsx` (list / add / test / delete / toggle)
- [ ] `SettingsDialog.tsx` — new "Cloud / Online" section

### Phase 3: Model selection + chat indicator (0.5–1 day)
- [ ] `CloudModelList.tsx` on models page, load via existing endpoint
- [ ] `ModelControlPanel` cloud conditional
- [ ] `ChatWindow` "Online · model via provider" indicator

### Phase 4: CLI (0.5 day)
- [ ] `sovereign cloud` group (add/list/remove/test/models)
- [ ] `_switch_mode` accepts `cloud`; help text updated

### Phase 5: Verification (0.5 day)
- [ ] `cd frontend && npm run build` (static export still clean)
- [ ] `npm run lint`
- [ ] Manual QA in dev: add OpenAI key → refresh models → load → chat streams → switch back to local model
- [ ] Packaged Electron QA (one platform) — cloud add/test/chat
- [ ] CLI: `cloud add/list/test/models` + `run <cloud-model> --mode cloud`

**Total: ~2.5–3.5 days.**

---

## 6. Error Handling → UI/CLI

Backend already returns mapped status codes (TODOS.md §10). Surface them without new machinery:

| Backend error | Frontend (toast) | CLI (rich) |
|---|---|---|
| 400 no key | "Add an API key in Settings → Cloud / Online" | `[red]Add a provider: sovereign cloud add[/red]` |
| 401 bad key | "API key rejected by {provider}" | `[red]API key rejected by {provider}[/red]` |
| 429 rate limit | "Rate limited by {provider}" | `[red]Rate limited — retry in {retry}s[/red]` |
| 504 timeout | "Could not reach {provider}" | `[red]Could not reach {provider}[/red]` |

`errMsg(error)` (already in `lib/utils.ts`) surfaces `error.detail` — the existing toast calls in `useModels` need no changes.

---

## 7. NOT in Scope (Deferred)

- **First-run onboarding wizard** — empty-state hint in settings covers it
- **Usage/billing dashboard** — no backend support yet
- **Per-provider key rotation UX** — edit = re-enter key, backend handles update
- **Electron tray/menu cloud shortcuts** — no desktop-only value yet
- **Offline fallback (cloud → local)** — deferred in TODOS.md, same here