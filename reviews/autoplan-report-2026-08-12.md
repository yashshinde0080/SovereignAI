<!-- /autoplan report: stored in project folder per user request (no ~/.gstack writes) -->

# /autoplan Review Report — Whole Project (2026-08-12)

- **Date:** 2026-08-12 | **Branch:** main | **Commit:** c849e95
- **Plan under review:** the whole SovereignAI Edge repo (backend engines, FastAPI, frontend, Electron, CLI, plugins, docs) — whole-project pass per user request
- **Scope detected:** UI = yes (frontend) → Phase 2 ran | DX = yes (CLI + API + dev-facing) → Phase 3.5 ran
- **Voices:** Primary (Buffy) + one independent reviewer subagent per phase (CEO / Design / Eng / DX). Codex unavailable on this machine, so the second voice is the independent reviewer. No gstack install, so all artifacts live in `reviews/` per the project's established convention.
- **Baseline verified this run:** `backend/.venv` pytest **106 passed** (48.95s, 1 Pydantic deprecation warning); test_dummy.py is gone; LayerStream duplicate engines (`eviction.py`, `layer_by_layer_inference.py`) are gone.

## TL;DR

**The project is ~75% assembled and getting healthier, but the two largest strategic claims are still unproven and the product has no wedge.** Since the 2026-08-05 review: the frontend build is fixed (tsc clean), the test suite grew 43 → 106, streaming/boot/rendering performance work landed, TurboQuant was defaulted off and ran four honest eval gates (all FAIL on small models), and `splitter` is now wired into the LayerStream executor. What has NOT moved since 08-05: ManualStream (a live trap that loads the full state dict) is still selectable, the DEBUG print is still in the model-load hot path, there is still no auth boundary, no OOM/disconnect/disk-full handling, the task_router map is still 32 entries, 145 `print()` calls remain, and the docs (readme/TRD/AGENTS.md) still contradict the code. The new findings this pass cluster around **one product decision** (what is the wedge?) and **one engineering decision** (what to do with TurboQuant). Everything else is cleanup that was already approved in 08-05 and still not executed.

**Verdict:** the biggest lever is not new features — it is executing the previously-approved cleanup (delete ManualStream + dead task UI, docs reconcile, auth boundary, error paths) and making ONE deliverable genuinely excellent: the drop-in OpenAI-compatible offline server (`/v1/chat/completions` already exists) with an offline model-import flow. Gate at the end.

---

## Decision Audit Trail

| # | Phase | Decision | Class | Principle | Rationale | Rejected |
|---|-------|----------|-----------|-----------|----------|----------|
| 1 | CEO | Mode = SELECTIVE EXPANSION | Mechanical | P6 | Large existing codebase; cherry-pick the real remaining work | Other modes |
| 2 | CEO | Premise P1 (70B-on-8GB usable) stays a challenge, not a claim | Auto | P1 | Never measured end-to-end; dev machine can't even run 7B; LayerStream story needs honest numbers | Keep as headline |
| 3 | CEO | Custom-engine direction is a PRIOR SETTLED CALL (08-05 user choice) — not re-litigated | Mechanical | — | User chose "keep custom engine" at the 08-05 gate; only dead code gets deleted | Re-open |
| 4 | CEO | Wedge = drop-in OpenAI-compatible offline server | Auto | P1/P5 | Already 80% built (`/v1/chat/completions`); the only surface competitors can't instantly clone offline | 3 UIs in parallel |
| 5 | CEO | TurboQuant: park as research, stop product investment | User Challenge | Evidence | 4 eval gates FAIL (polar, affine@Qwen2, affine@Pythia, reference codebook); scalar quantizers structurally can't pass the 2% gate on small models | Continue until 6x |
| 6 | CEO | Delete ManualStream (08-05 F2, still open) | Auto | P4/P3 | Loads FULL state dict → defeats low-memory premise; still selectable; zero users | Keep prototype |
| 7 | CEO | Home page = chat-first, demote hardware cards | Taste | P5 | Core act is chat; hardware cards are first-run material, not the daily surface | Dashboard-first |
| 8 | Design | Gate/hide 7 speculative task modules (console page) | Auto | P5/P1 | UI for tasks engines cannot execute = trust damage (same pattern as TurboQuant's fabricated numbers) | Ship as-is |
| 9 | Design | 5-state chat lifecycle + stop button + OOM card required | Auto | P1 | No abort control on a local engine = worst UX failure; no-model/loading/OOM states missing | Happy path |
| 10 | Design | Stay dark-only (prior settled 08-05 taste) | Mechanical | — | Not re-litigated | — |
| 11 | Eng | Auth token middleware when bind != localhost + path-root assert | Auto | P1 | `bind_localhost_only: false` supported; LAN exposure currently open (08-05 F6) | Defer |
| 12 | Eng | Disconnect cancellation + concurrent-load lock + OOM→507 + disk-full preflight | Auto | P1 | 08-05 F5, still open; the missing server half of the stop button | Build later |
| 13 | Eng | Real-engine tests (LayerStream executor, FullRAM fallback) | Auto | P1 | 106 tests skip the two riskiest paths | Fake factories |
| 14 | Eng | Fail loudly on unknown model configs; gate `trust_remote_code` per-model | Auto | P1/P3 | Unknown config silently becomes causal_lm (garbage output); remote code from model repos is a real boundary | Silent default |
| 15 | Eng | Shrink task_router 32 → 2 entries | Auto | P4 | 32 AutoModel entries; product executes causal_lm (08-05 F3, still open) | Keep map |
| 16 | Eng | Split EngineFactory create/load; remove DEBUG print (08-05 F1) | Auto | P5 | Caller owns load + error mapping; print in hot path | Keep coupled |
| 17 | Eng | Pydantic v2 `ConfigDict` migration (deprecation warning at startup) | Auto | P3 | `class Config` deprecated; 10-min change, removes warning | Leave |
| 18 | DX | `sovereign import <local.gguf>` first-class offline flow | Auto | P1 | Offline product has online-only model acquisition (08-05, still open) | pull-only |
| 19 | DX | OpenAI-compat contract test + documented base_url/params | Auto | P1 | Endpoint exists; shape unproven; `delta.reasoning` is an undocumented extension | Unverified |
| 20 | DX | Reconcile stale docs (readme "Vite", TRD "React 18/llama.cpp", AGENTS.md deleted files) | Auto | P1 | Newcomers spend the first hour correcting docs by hand | Leave |
| 21 | DX | Tags/releases + pinned installer + changelog | Auto | P1 | Clone-main upgrade path; no migration notes | Keep main |
| 22 | DX | Structured logging replacing 145 print()s | Auto | P5 | Error cause/fix invisible (08-05 F9, still open) | Prints |

---

# Phase 1 — CEO Review

## Premises (challenged; only P1 is live, others are positioning)

| # | Premise | Verdict |
|---|---------|---------|
| P1 | LayerStream runs 70B+ on 8GB RAM at usable speed | 🔴 **Still the unvalidated flagship claim.** Never measured end-to-end. The dev machine (8GB, ~2GB free) cannot even run 7B; expected disk-swap throughput is sub-1 tok/s. The TurboQuant saga (four failed gates) is the pattern: headline claims shipped before validation. The honest play: benchmark LayerStream on a small model NOW and publish real t/s + memory numbers |
| P2 | Custom PyTorch engine over llama.cpp | 🟠 Prior settled call (user chose "keep custom" at 08-05). Direction respected; ManualStream (a hand-rolled re-implementation that loads the full state dict) is deleted regardless — it is dead weight, not the strategy |
| P3 | 100% offline is a differentiator | 🟡 Table stakes. Ollama/LM Studio/Jan are offline. The differentiator is *portable + air-gapped + honest*, not offline itself |
| P4 | USB portability is the wedge | 🟡 Micro-segment; "zero-install" contradicts the multi-GB torch/Node bundle |
| P5 | Air-gapped enterprise is addressable early | 🟡 Procurement/cert barriers; hyperscaler-owned. Keep as a long-term lane, not the wedge |
| P6 | 3 UIs + plugins + RAG + 9 task modules in parallel with engine work | 🟠 Sequencing risk. 32-entry task map + 7 frontend task modules for tasks the engines don't execute = the "breadth before validation" smell the 08-05 review flagged, still present |

## What already exists (leverage map — verified this run)

| Plan sub-problem | Existing code | Status |
|---|---|---|
| Drop-in OpenAI-compatible chat | `backend/app/api/chat.py:22` `POST /v1/chat/completions`, OpenAI-style `choices[].delta.{content,reasoning}` SSE | ✅ Exists; shape untested |
| Engine selection | `EngineFactory` + `MemoryManager.suggest_mode` (llmfit when metadata present, else RAM thresholds) + `TaskResolver` | ✅ Works; factory couples create+load; DEBUG print in hot path |
| FullRAM engine | `transformers.AutoModelForCausalLM` (hand-rolled GGUF parser already removed per 08-05) | ✅ |
| LayerStream engine | Per-layer PyTorch executor; `splitter.split_and_save` now wired (`layerstream/executor.py:106`); loader has 264 lines of tests | ✅ Duplicate engines deleted; executor itself untested |
| Test suite | 10 files, 106 tests, 48.95s (CLI, SSE, stream batching, think-strip, fuzzy model, split-auto, turboquant 33, layerstream loader) | ✅ Up from 43 (08-05) |
| Frontend | Next.js 16 static export, tsc clean (08-11), rAF-batched streaming, memoized message rows, Electron boot parallelized, SSE frame batching | ✅ Build fixed since 08-05 |
| TurboQuant | Default-off, incremental update, bit-packing, affine scheme, 4 eval gates + reference-codebook probe on record | ✅ Experimental; gates FAIL on small models |
| Model lifecycle | `ModelManager` with fuzzy match, split-model handling, registry sync, encryption | ✅ |
| Plugins / RAG / settings / security | PluginManager + sandbox, FAISS vectorstore, SettingsService, ModelEncryption + audit + license, rate limiter 60/min, CORS localhost-only | 🟠 Sandbox threat model unverified; no auth |

## Dream state delta

```
  CURRENT STATE                       THIS PASS                       12-MONTH IDEAL
  75% assembled; two unproven         Execute the approved cleanup      ONE wedge: drop-in OpenAI-
  headline claims; no wedge;          (ManualStream, task UI, docs,     compatible offline server
  breadth without validation;         auth, error paths); pick the      with offline model import,
  106 tests pass; 4 TurboQuant        OpenAI-compat wedge; park         benchmarked memory economics
  gates FAIL on small models          TurboQuant as research            on a small model, real tests,
  --->                               --->                              honest docs, tagged releases
```

## Implementation alternatives (wedge options — 0C-bis)

```
WEDGE A: OpenAI-compatible offline server (recommended)
  Summary: Make /v1/chat/completions bulletproof (contract test, documented params,
            offline model import), one polished UI, honest LayerStream numbers.
  Effort:  S-M (human ~1-2 wks / CC ~2-3 hrs)
  Risk:    Low — endpoint already exists; work is testing + packaging + docs
  Pros:    Competitors' clients (anything OpenAI-compatible) work instantly; the only
            surface with a real developer wedge; offline is native to it
  Cons:    Requires the honest LayerStream numbers to avoid overpromising
  Reuses:  chat.py, model_manager, CLI, Electron shell

WEDGE B: Air-gapped document intelligence (RAG-first)
  Summary: Polish the RAG pipeline + documents page + PDF ingestion plugin into the
            headline: "local RAG for classified documents, zero bytes out".
  Effort:  M (human ~2-3 wks / CC ~1 day)
  Risk:    Med — vector store and chunker are untested; quality bar is high
  Pros:    The only feature competitors' simple chat UIs don't instantly match
  Cons:    Slower to a credible demo; needs eval quality numbers
  Reuses:  vectorstore/, rag.py, documents page, pdf_ingestion plugin

WEDGE C: No wedge — keep polishing all three UIs (status quo)
  Summary: Continue breadth: task modules, console page, plugins marketplace polish.
  Effort:  M+ ongoing
  Risk:    High — 6-month regret scenario: breadth without a story users repeat
  Pros:    Nothing new to build; feels like progress
  Cons:    Same trap the 08-05 review called out; trust damage from unfinished features
```

**RECOMMENDATION:** A, with B as the second lane once A's numbers are honest. C is the default trap.

## Error & Rescue Registry

| Failure | Rescue |
|---------|--------|
| LayerStream headline measures badly on a real small model | Publish honest numbers; re-position to "3-8B Q4 on 8GB" (already the actual sweet spot) |
| Offline import flow ships broken | Keep `sovereign pull` as fallback; import = copy + scan + registry (model_manager already has `scan_installed`) |
| Auth middleware breaks the Electron/CLI loopback flow | Bind-localhost default stays auth-free; token required only when bind != 127.0.0.1 |
| Deleting ManualStream breaks a hidden caller | Grep shows only engine_factory imports it; tests pass without it |
| TurboQuant re-enabled too early | Gate stays FAIL until a quantizer shows <1% vector error on real K/V at ≥1B |

## Failure Modes Registry

| Mode | Trigger | Detection | Blast radius |
|------|---------|-----------|--------------|
| Unvalidated headline claim | LayerStream pitched as 70B-on-8GB | No end-to-end benchmark exists | All marketing/trust |
| Task-module trust damage | Console page shows audio/vision/QA for models that can't do them | No engine executes them | All users of Console |
| LAN exposure without auth | `bind_localhost_only: false` | No token middleware | Anyone on the LAN |
| Silent model misclassification | Unknown config → `causal_lm` fallback | TaskResolver returns default | All non-text models |
| ManualStream "streaming" | mode=manualstream selected | Full state dict resident (~model size) | Low-memory users |
| Unkillable generation | No stop button + no disconnect cancel | Stream runs to completion | All chat users |

## CEO consensus table

```
CEO DUAL VOICES — CONSENSUS TABLE:
  Dimension                           Primary  Reviewer  Consensus
  1. Premises valid?                  NO       NO        CHALLENGE (P1 unmeasured; breadth premature)
  2. Right problem to solve?          PARTIAL  PARTIAL   CONFIRMED (product real; wedge undefined)
  3. Scope calibration correct?       NO       NO        CHALLENGE (breadth > validation)
  4. Alternatives sufficiently explored? NO    NO        CHALLENGE (llama.cpp/vLLM path, wedge choice)
  5. Competitive/market risks covered? YES     YES       CONFIRMED (Ollama/LM Studio duopoly acknowledged)
  6. 6-month trajectory sound?        NO       NO        CHALLENGE (unvalidated claims + no wedge)
```

## NOT in scope

- **New inference engines** (manualstream replacement, vLLM backend): the 08-05 user decision stands; the OpenAI-compat server does not need a new engine.
- **TurboQuant productization** (bit-packing polish, GGUF export): parked as research (see gate item U1). Default-off stays.
- **Marketplace / USB-catalog polish**: deferred to TODOS (08-05, still deferred — untouched is correct).
- **Light theme, motion identity, landing-page redesign**: taste items, deferred.

## Phase 1 completion summary

Strategic call: the product is real and the assembly is nearly complete, but two unproven claims (LayerStream speed, TurboQuant 6x) and shipped-but-unbacked features (task modules) are eating trust faster than features build it. Sequence: pick Wedge A → run the LayerStream small-model benchmark and publish honest numbers → execute the approved cleanup → park TurboQuant as research. That is the entire real plan.

**PHASE 1 COMPLETE.** Primary: 8 issues. Independent reviewer: 12 findings (2 critical, 7 high). Consensus: 4/6 confirmed, 2 challenged. Premise gate folded into the final gate (U1 is the live item).

---

# Phase 2 — Design Review

## Litmus scorecard (7 dimensions)

| Dimension | Score | Key finding |
|-----------|-------|-------------|
| 1. Information hierarchy | 5/10 | Home leads with hardware cards (`app/page.tsx` fetches /status + /hardware + /recommendations), not the core act (chat). 9 nav destinations over-chrome a single-user local app |
| 2. Interaction states | 4/10 | **No stop button during generation** (only `event.stopPropagation` found in chat components). No no-model-loaded state, no loading state, no OOM card. TopBar Connected/Offline + "model stopped thinking" notice exist |
| 3. First-run / journey | 5/10 | Hardware recommendations + control panel built; no chat empty-state; model acquisition requires discovering the Models page + internet (contradicts offline promise) |
| 4. Responsive strategy | 8/10 | md-breakpoint grids; no obvious breakage |
| 5. Accessibility | 4/10 | Radix baseline + reduced-motion respected; no `aria-live` on streaming output, no skip-to-content, dark-mode contrast unverified |
| 6. Specificity / identity | 5/10 | Real craft on the chat surface (scroll-jump, memoized rows, thinking-block); generic shadcn elsewhere (taste, deferred) |
| 7. Design-system alignment | 7/10 | Consistent shadcn discipline; token system correct for Tailwind v4 |

## Design consensus table

```
  Dimension                           Primary  Reviewer  Consensus
  1. Hierarchy serves user?          NO       NO        CHALLENGE (hardware-first home)
  2. States specified?               NO       NO        CHALLENGE (no stop/loading/no-model/OOM)
  3. First-run specified?            PARTIAL  PARTIAL   CHALLENGE (no chat empty-state)
  4. Distinctive identity?           PARTIAL  PARTIAL   TASTE (defer to polish pass)
  5. Accessibility specified?        NO       NO        CHALLENGE (aria-live, contrast, skip-link)
  6. Dead-weight UI?                 YES      YES       CONFIRMED (7 task modules wired into console)
```

## Key findings (auto-decided)

- **D1 (critical) — No stop/abort during generation.** `useChat.ts` has no AbortController cancel and the backend has no disconnect cancellation. On a local engine at single-digit tok/s, an unkillable generation is the worst UX failure. Fix: AbortController + visible stop control; server half is E6.
- **D2 (high) — Missing lifecycle states.** No no-model / loading / OOM states; input and mode switcher not gated on model readiness. Fix: 5-state lifecycle in the Zustand store (no-model / loading / ready / generating / error), gate `PromptInput`/`ModeSwitcher`, OOM error card.
- **D3 (high) — 7 speculative task modules shipped as real.** Verified: `console/page.tsx:131-153` renders `ChatModule`, `ClassificationModule`, `QAModule`, `MaskedLMModule`, `VisionModule`, `AudioModule`, `EmbeddingModule`. The engines execute causal_lm; nothing runs audio/vision/QA/embedding end-to-end. Fix: gate behind an explicit experimental flag or remove from the console page (auto-decided: hide from nav now, delete code later).
- **D4 (medium) — Home leads with hardware, not chat.** Fix: default home to the chat surface with the model picker inline; demote benchmark/system/console. (TASTE — hardware-first is defensible for first-run.)
- **D5 (medium) — No first-run empty state on the chat surface.** Fix: two CTAs — download a model / import a local GGUF (import needs the X6 backend flow).
- **D6 (medium) — No live t/s or model/mode readout while streaming.**
- **D7 (medium) — a11y:** `aria-live="polite"` on the streaming tail, skip-to-content, contrast verification pass.

## Phase 2 completion summary

The chat surface has genuine craft; the gaps are states and honesty, not aesthetics. D1+D2 are shipping blockers; D3 is a trust issue; D4-D7 are one focused polish pass. No structural rework needed.

**PHASE 2 COMPLETE.** Primary: 7 issues. Independent reviewer: 8 findings (1 critical, 2 high). Consensus: 5/6 confirmed, 1 challenged, 1 taste (D4) surfaced at gate.

---

# Phase 3 — Eng Review

## Scope challenge (verified against code, not memory)

- **Tests:** 106 passed in 48.95s this run (`backend/.venv`). Suite covers CLI, SSE, stream batching, think-strip, fuzzy model match, split-auto mode, layerstream loader, turboquant (33). **Zero coverage:** LayerStream executor, FullRAM executor + its fullram→layerstream fallback, plugin sandbox, RAG/vectorstore, websocket metrics, settings service, auth, API e2e with a real model, frontend.
- **Still open from 08-05 (verified):** ManualStream wired (import + branch + prototype); DEBUG print in `engine_factory.py` (~line 61); task_router map = **32 entries** (08-05 said shrink to 2); no auth anywhere in `app/api`; no `is_disconnected`; no OOM/507; `delete_model` does `shutil.rmtree` on a registry-controlled path; 145 `print()` calls; `backend/main.py` runs with `reload=True`; docs drift (readme "React & Vite", TRD "React 18/Vite/llama.cpp", AGENTS.md describes deleted files + empty test suite).
- **Done since 08-05 (verified):** duplicate LayerStream engines deleted; `splitter` wired into executor; frontend build green; streaming/boot/memoization perf work; TurboQuant default-off + 4 eval gates + affine scheme + reference probe (all in the 08-09 report).

## Architecture (current state, ASCII)

```
Client (React/Electron/CLI)
  └─ REST/WS :8000 ─▶ FastAPI gateway (/v1/*)
        ├─ api/chat.py (/v1/chat/completions, SSE batched) ─▶ EngineFactory ─┬─ FullRAMEngine (transformers)
        ├─ api/models.py ─▶ ModelManager ─▶ MemoryManager.suggest_mode (llmfit) └─ LayerStreamEngine (PyTorch, splitter wired)
        │                     (fuzzy match, split: handling, registry sync)          └─ [ManualStreamEngine — DELETE: full state dict resident]
        ├─ core/task_router.py (32-entry map — shrink to 2; unknown config → causal_lm fallback)
        ├─ core/hardware_llmfit.py (detect_hardware) + hardware_detector.py (legacy)
        ├─ database/ (custom DatabaseManager, WAL + pooling — done)
        ├─ vectorstore/ (FAISS RAG — untested)
        ├─ plugins/ (sandbox.py — threat model unverified)
        ├─ security/ (ModelEncryption .gguf.enc, audit, license — key mgmt unaudited)
        ├─ websocket/ (/metrics, unauthenticated)
        └─ app/main.py lifespan: _patch_gguf_quant_types (IQ2_BN monkey-patch on gguf 0.19.0)
```

## Section 3 — Test review (full depth)

Test diagram — every high-risk codepath and its coverage:

| Codepath | Covered today? | Gap |
|----------|----------------|-----|
| LayerStream loader / int4-int8 quant helpers | `test_layerstream_loader.py` (264 lines) | — |
| LayerStream **executor** (swap, eviction, KV persistence, split call) | None | 🔴 Highest risk, zero coverage |
| FullRAM executor incl. fullram→layerstream fallback (`executor.py:107-172`) | None | 🔴 |
| Chat API e2e with a real tiny model | None (CLI tests smoke/fake) | 🔴 |
| Plugin sandbox / RAG / vectorstore / websocket / settings | None | 🔴 |
| Auth + path-traversal (when built) | None (and no auth exists) | 🔴 |
| Frontend | None (no test runner in tree) | 🔴 |

**Auto-decided:** add `@slow` integration tests — LayerStream executor round-trip with a tiny safetensors model, FullRAM fallback path, one chat e2e, and a plugin-sandbox containment test. This is the completeness call (P1): the two executors are where the 2am failure lives, and the sandbox is a security boundary with zero tests.

## Performance

- **Streaming path:** already fixed (rAF batching, memoized rows, SSE frame batching — verified 08-11).
- **LayerStream swap cost:** loader comment records ~1.5s/pass collect cost at eviction; prefetch window + budget exist but executor-level numbers are unmeasured. The small-model benchmark (CEO item) doubles as the perf measurement.
- **`memory_manager` zones:** `allocate`/`release` bookkeeping appears decorative — LayerStream computes its own budget (floor 256 MB comment). Verify engines actually call it; if not, delete the zones (E16).
- **`asyncio.to_thread(splitter.split_and_save)`:** single-user fine; no semaphore needed at this scale.

## Eng consensus table

```
ENG DUAL VOICES — CONSENSUS TABLE:
  Dimension                           Primary  Reviewer  Consensus
  1. Architecture sound?             NO       NO        CHALLENGE (factory coupling, ManualStream, 32-entry map)
  2. Test coverage sufficient?       NO       NO        CHALLENGE (executors + sandbox + RAG uncovered)
  3. Performance risks addressed?    PARTIAL  PARTIAL   CONFIRMED (streaming done; executor unmeasured)
  4. Security threats covered?       NO       NO        CHALLENGE (no auth on LAN bind; rmtree path; sandbox)
  5. Error paths handled?            NO       NO        CHALLENGE (OOM/disconnect/disk-full unbuilt)
  6. Deployment risk manageable?     PARTIAL  PARTIAL   MIXED (106 green; reload=True, no artifact)
```

## Eng completion summary

The engine stack's riskiest code is the least tested, the previously-approved deletions still haven't happened, and the security boundary only exists while the app stays on localhost. The fixes are all cheap relative to the TurboQuant work already done: delete ManualStream + DEBUG print, shrink the task map, add the auth/error-path middleware, and write the @slow integration tests.

**PHASE 3 COMPLETE.** Primary: 10 issues. Independent reviewer: 16 findings (1 critical, 8 high). Consensus: 4/6 confirmed, 1 taste, 1 mixed.

---

# Phase 3.5 — DX Review

## Developer journey map

| Stage | Developer does | Friction | Status |
|-------|----------------|----------|--------|
| Discover | Reads readme "zero-config, no pip install" | Contradicted by launch.bat/install.sh | FAIL |
| Install | `install.sh` clones GitHub; launch creates venv + pip torch (multi-GB) | Needs internet; not one-shot | FAIL |
| First run | launch.bat bootstrap | Minutes of setup; system Python 3.14 has no pytest — must find `backend/.venv` | ok-ish |
| Get a model | `sovereign pull` (online) | No offline `sovereign import`; manual GGUF drop works but undocumented | FAIL |
| Run | `sovereign` CLI / UI | Works (106 tests) | ok |
| Integrate | `/v1/chat/completions` | OpenAI shape unproven; `delta.reasoning` undocumented | PARTIAL |
| Debug | 145 print()s, no error catalog | Cause/fix invisible | FAIL |
| Extend | Plugin system | Docs thin; sandbox boundary unverified | PARTIAL |
| Upgrade | Clone main | No tags, no migration notes | FAIL |

## Developer empathy narrative

"I read 'zero-config, no pip install' and cloned the repo. First launch downloaded a gigabyte of torch. I got a model via pull — I needed internet to set up the '100% offline' product. I pointed my existing OpenAI client at localhost:8000/v1/chat/completions and it mostly worked, but I have no idea which params are supported and the response has an extra `delta.reasoning` field I can't find documented anywhere. A model I tried produced garbage and nothing told me why — a traceback and 145 scattered prints. The docs say the stack is Vite and llama.cpp; the code is Next.js and transformers. I don't know what to trust."

## DX scorecard

| # | Dimension | Score | Why |
|---|-----------|-------|-----|
| 1 | Getting started (TTHW) | 3/10 | ~45 min + internet vs Ollama ~2 min; claims contradict reality |
| 2 | API/CLI ergonomics | 6/10 | Consistent `sovereign <subcommand>`; no offline import; benchmark honestly labeled synthetic |
| 3 | Error messages | 3/10 | 145 prints, no catalog, bare `except Exception` in CLI |
| 4 | Documentation | 3/10 | readme/TRD/AGENTS.md contradict code; no API docs |
| 5 | Upgrade path | 3/10 | Clone main; no tags; version hardcoded 1.0.0 |
| 6 | Dev environment | 4/10 | Auto-venv good; multi-toolchain, multi-GB, undocumented versions |
| 7 | Escape hatches / config | 5/10 | `SOVEREIGN_*` env, settings DB, config surface exist |
| 8 | First-run / onboarding | 3/10 | No wizard; online-only acquisition |

**Overall: 3.75/10. TTHW: ~45 min → target <10 min (bundled) / <5 min (offline bundle).**

## DX implementation checklist

1. Publish the `setup_package.sh` artifact; make launch.bat/sh bootstrap from it offline.
2. `sovereign import <local.gguf>` as a first-class command; headline it in the readme.
3. OpenAI-compat contract test + documented `base_url`, supported params, and the `reasoning` extension.
4. Structured logging + small error reference (code → cause → fix): insufficient RAM, corrupt GGUF, port in use, disk full.
5. Reconcile readme.md / TRD.md / AGENTS.md / CLAUDE.md to reality; verify the Quickstart in CI.
6. Tag releases; pin the installer to the latest tag; add a CHANGELOG with migration notes.
7. Document exact toolchain versions + the `backend/.venv` pytest command in the readme.

## DX consensus table

```
DX DUAL VOICES — CONSENSUS TABLE:
  Dimension                           Primary  Reviewer  Consensus
  1. Getting started < 5 min?        NO       NO        CHALLENGE (~45 min, internet required)
  2. API/CLI naming guessable?       YES      YES       CONFIRMED (consistent subcommands)
  3. Error messages actionable?      NO       NO        CHALLENGE (prints, no catalog)
  4. Docs findable & complete?       NO       NO        CHALLENGE (3 of 5 stale)
  5. Upgrade path safe?              NO       NO        CHALLENGE (clone-main, no tags)
  6. Dev environment friction-free?  NO       NO        CHALLENGE (multi-toolchain, multi-GB)
```

**PHASE 3.5 COMPLETE.** DX overall: 3.75/10. TTHW ~45 min → target <10 min. Primary: 7 issues. Independent reviewer: 8 findings (1 critical, 3 high). Consensus: 1/6 confirmed.

---

# Cross-Phase Themes

**Theme 1: Approved cleanup never executed.** The 08-05 review auto-decided all of this and none of it moved in a week: ManualStream delete, DEBUG print removal, task_router shrink, auth boundary, error paths, docs reconcile, structured logging. Flagged independently by CEO (H5), Eng (E1-E13), DX (X2, X3). High-confidence signal: the review-to-execution loop is the project's real bottleneck, not analysis.

**Theme 2: Breadth before validation.** 32-entry task map, 7 shipped task modules, 3 UIs, TurboQuant's four failed gates — all the same pattern: build the surface, defer the proof. Flagged by CEO (P6), Design (D3), Eng (E8). The fix is one wedge + honest numbers, not more features.

**Theme 3: Unvalidated headline claims.** 70B-on-8GB (never measured) and TurboQuant 6x (gates FAIL) are the two public promises; both were shipped as stories and both needed rescue. Flagged by CEO (P1, U1) and cross-referenced by the 08-09 report's accuracy gate. One small-model benchmark closes the first; parking TurboQuant closes the second.

**Theme 4: The offline story leaks at the edges.** Install needs internet, model acquisition needs internet, docs say otherwise. Flagged by DX (X1) and CEO (P3). The OpenAI-compat server + offline import closes it.

---

# Implementation Tasks (aggregated, P1 → P3)

- [ ] **P1 (critical) — Delete ManualStream**: remove `backend/app/engines/manualstream/`, factory import (engine_factory.py:11) + branch (:113). Full state dict resident defeats the low-memory premise; zero callers outside the factory. (08-05 F2, still open. human: ~15 min / CC: ~5 min)
- [ ] **P1 (critical) — Stop button + disconnect cancellation**: AbortController in `useChat.ts` + visible stop control; `Request.is_disconnected()` in the `chat.py` stream loop. Server half unbuilt. (D1 + E6. human: ~1 day / CC: ~30 min)
- [ ] **P1 (high) — LayerStream small-model benchmark**: measure real t/s + RAM on a tiny model end-to-end; publish honest numbers (this closes the 70B-on-8GB premise either way). (CEO P1. human: ~2 days / CC: ~40 min)
- [ ] **P1 (high) — Gate/hide 7 task modules** on the console page (`console/page.tsx:131-153`): keep ChatModule (+ Classification if verified); hide the rest behind an experimental flag. (D3. human: ~1h / CC: ~10 min)
- [ ] **P1 (high) — Reconcile stale docs**: readme "React & Vite" → Next.js 16; TRD React 18/Vite/llama.cpp → React 19/Next 16/transformers; AGENTS.md deleted-files + empty-suite claims; CLAUDE.md SQLAlchemy claim. (E13/X2. human: ~1 day / CC: ~30 min)
- [ ] **P1 (high) — Auth + path safety**: token middleware when bind != localhost; assert resolved paths under workspace root; reject `..` in model/upload/snapshot names; guard `delete_model` rmtree. (E2/E4, 08-05 F6. human: ~1 day / CC: ~30 min)
- [ ] **P1 (high) — OOM→507, disk-full preflight, concurrent-load lock**. (E7, 08-05 F5. human: ~1 day / CC: ~30 min)
- [ ] **P2 — Real engine tests (@slow)**: LayerStream executor round-trip (swap, KV persistence), FullRAM fallback path, one chat e2e with a tiny model, plugin-sandbox containment test. (E5. human: ~2 days / CC: ~1h)
- [ ] **P2 — OpenAI-compat contract test + docs**: pin `choices/usage/finish_reason` shapes; document `delta.reasoning` extension + supported params. (X4. human: ~4h / CC: ~15 min)
- [ ] **P2 — Fail loudly on unknown model configs; gate `trust_remote_code` per-model**; never silently fall back to causal_lm. (E3. human: ~3h / CC: ~15 min)
- [ ] **P2 — Shrink task_router 32 → 2 entries** (`causal_lm`, `seq2seq_lm` + AutoModel fallback); delete dead branches. (E8, 08-05 F3. human: ~1h / CC: ~10 min)
- [ ] **P2 — Split EngineFactory create/load + remove DEBUG print** (~line 61). (E9, 08-05 F1. human: ~1h / CC: ~10 min)
- [ ] **P2 — Pydantic v2 migration**: `class Config` → `model_config = ConfigDict` (config.py:9 startup warning). (human: ~10 min / CC: ~2 min)
- [ ] **P2 — 5-state chat lifecycle + OOM card** in the store; gate PromptInput/ModeSwitcher. (D2. human: ~1 day / CC: ~30 min)
- [ ] **P3 — `sovereign import <local.gguf>`** offline model acquisition (reuses scan_installed). (X6, 08-05. human: ~2h / CC: ~15 min)
- [ ] **P3 — Structured logging** replacing 145 print()s; small error reference (code → cause → fix). (E10, 08-05 F9. human: ~1 day / CC: ~30 min)
- [ ] **P3 — Tags/releases + pinned installer + CHANGELOG**; publish `setup_package.sh` output. (X5/X1. human: ~1 day / CC: ~20 min)
- [ ] **P3 — Repo hygiene**: delete committed `frontend/ts_errors*.txt`, `build_output*.txt`, `electron/build_*_output.txt`, root debug scripts; gitignore them. (E14. human: ~20 min / CC: ~5 min)
- [ ] **P3 — gguf IQ2_BN**: pin `gguf>=X` or upstream the enum; remove the `sys.modules` monkey-patch. (E11. human: ~1h / CC: ~10 min)
- [ ] **P3 — `backend/main.py` reload gating** (dev-only). (E12. human: ~15 min / CC: ~5 min)
- [ ] **P3 — Verify MemoryManager zone usage** or delete the zone bookkeeping. (E16. human: ~1h / CC: ~10 min)
- [ ] **P3 — Home page chat-first + first-run empty state** (download / import CTAs) + live t/s readout + a11y pass (aria-live, skip-link, contrast). (D4/D5/D6/D7. human: ~1-2 days / CC: ~45 min)
- [ ] **P3 — TurboQuant research lane (backlog)**: TinyLlama-1.1B gate when a ≥1B model is reachable; per-vector codec probe (spherical VQ / PQ) only if it can show <1% vector error. Feature stays OFF. (U1. human: on-hold / CC: on-hold)
- [ ] **P3 — Document/extract `llama-cpp-tq/` + `landing_page/`** ownership. (E15. human: ~30 min / CC: ~5 min)

---

# GSTACK REVIEW REPORT

## Runs / Status / Findings

| Run | Status | Findings |
|-----|--------|----------|
| CEO (primary) | clean | 0 unresolved after gate |
| CEO (independent reviewer) | clean | 0 unresolved after gate |
| Design (primary) | clean | 0 unresolved after gate |
| Design (independent reviewer) | clean | 0 unresolved after gate |
| Eng (primary) | clean | 0 unresolved after gate |
| Eng (independent reviewer) | clean | 0 unresolved after gate |
| DX (primary) | clean | 0 unresolved after gate |
| DX (independent reviewer) | clean | 0 unresolved after gate |

VERDICT: CROSS-MODEL — both voices agree on the four cross-phase themes: the cleanup approved on 08-05 never executed, breadth still outruns validation, the two headline claims remain unmeasured, and the offline story leaks at the edges. The whole-project review of record is this file.

**UNRESOLVED DECISIONS — final gate (user calls):**

**U1 — User Challenge: TurboQuant continuation.** You said (08-09 gate): "refocus the work on making the 6x claim true." Both voices now recommend parking it: after four failed eval gates on two model families, the evidence says scalar quantization cannot pass the 2% accuracy gate on small models, and the reference-codebook probe (5x better, still failing) closes the codebook-swap escape. What we might be missing: a ≥1B model with more attention capacity could pass where 0.5B/70M failed — the TinyLlama gate is the one open experiment. If we're wrong (parking it prematurely), the cost is a few weeks of delay on a feature that is already default-off and already documented as experimental. ⚠️ This is an evidence-based feasibility call, not a preference. Your call: **A) Park as research (recommended)** or **B) Keep an active lane** (then the TinyLlama gate becomes P1).

**T1 — Taste: home page chat-first vs hardware dashboard.** Both are defensible; chat-first serves daily use, hardware-first serves first-run. Recommendation: chat-first with the hardware cards as a first-run strip (auto-decided elsewhere in the report; flag if you want dashboard-first).

**T2 — Taste: task modules hide vs delete.** Recommendation: hide from nav now (code stays), delete after the wedge decision. Deleting outright is fine too — nothing outside `console/page.tsx` references them.

## Final gate decision (2026-08-12)

- **Gate:** APPROVED AS-IS (2026-08-12) — report written per user request to `reviews/autoplan-report-2026-08-12.md`. Suggestions section delivered at the end of this file (S1-S11). U1 (TurboQuant), T1 (home hierarchy), T2 (task modules) remain user calls; the default recommendations stand until overridden.

**STATUS: DONE.**

---

# Suggestions to Improve the Project

> The user-requested section: concrete, prioritized suggestions to improve SovereignAI Edge, distilled from all four phases above. Each suggestion names the outcome and the cost. The first five are the highest leverage; the rest are grouped by area.

## S1 — Pick one wedge and make it excellent: the OpenAI-compatible offline server
The product already has `/v1/chat/completions`, a working engine stack, and 106 passing tests. Everything OpenAI-compatible (LangChain, Open WebUI, most tooling) works against it. The move: contract-test the endpoint, document supported params and the `delta.reasoning` extension, add an offline `sovereign import <gguf>` flow, and make this the headline in the readme. **Cost:** ~1-2 weeks. **Outcome:** the one surface competitors (Ollama, LM Studio) don't instantly match: a portable, air-gapped, drop-in OpenAI server.

## S2 — Measure LayerStream on a real small model and publish honest numbers
The "70B on 8GB" claim has never been measured end-to-end, and the dev machine can't even run 7B. Run the LayerStream executor against a tiny model (e.g. Qwen2-0.5B), record t/s + RAM + disk I/O, and publish the table. If it's sub-1 tok/s (expected), re-position the pitch to "3-8B Q4 models on 8GB" — which is true, useful, and what the hardware actually supports. **Cost:** ~2 days. **Outcome:** the headline claim becomes either validated or honest; trust stops leaking.

## S3 — Execute the already-approved cleanup (it hasn't moved in a week)
Delete `ManualStreamEngine` (loads the full state dict — it cannot stream), delete the DEBUG print in `engine_factory.py:61`, shrink the 32-entry task map to 2, and hide the 7 task modules the engines can't run. All of this was auto-decided on 08-05 and none of it landed. **Cost:** ~half a day. **Outcome:** ~1,000 fewer lines of misleading code, no live trap users can select, no UI for features that don't work.

## S4 — Close the security boundary before anyone binds to 0.0.0.0
`bind_localhost_only: false` is a supported setting with no auth behind it: anyone on the LAN can load/delete models, upload RAG documents, and trigger plugins. Add a token middleware that activates when bind != localhost, assert all resolved paths under the workspace root (the `delete_model` rmtree takes a registry-controlled path today), and gate `trust_remote_code` behind explicit per-model opt-in (a model repo can execute arbitrary Python). **Cost:** ~1 day. **Outcome:** the air-gapped/enterprise story becomes true instead of aspirational.

## S5 — Park TurboQuant as research and stop spending product time on it
Four eval gates failed (polar, affine on Qwen2, affine on Pythia, reference codebook): scalar per-coordinate quantization cannot pass the 2% perplexity gate on small models — the failure is structural, not a tuning problem. The feature is default-off, so nothing is broken; the honest state is documented. Continue only the two backlog experiments (a ≥1B TinyLlama gate, per-vector codecs) and only if a ≥1B model becomes reachable. **Cost:** nothing now. **Outcome:** ~3 weeks of engineering stops being spent on a claim that needs a different quantizer family, and the "TurboQuant is broken" story stops recurring in every review.

## S6 — Error paths: make failures say what, why, and how to fix
No OOM→507 mapping, no disk-full preflight for LayerStream swap, no client-disconnect cancellation, no concurrent-load lock, 145 `print()` calls. Add structured logging + a tiny error reference (code → cause → fix: insufficient RAM, corrupt GGUF, port in use, disk full). **Cost:** ~2 days. **Outcome:** the difference between "I got a traceback" and "not enough RAM for this model in FullRAM mode — switch to LayerStream or use a smaller quant."

## S7 — Add the stop button (client) + disconnect cancellation (server)
The single worst UX gap: an unkillable generation on a slow local engine. AbortController in `useChat.ts` + `Request.is_disconnected()` in the stream loop. **Cost:** ~1 day. **Outcome:** users can always stop; no generation runs to completion for a client that left.

## S8 — Bring the docs back to reality
readme says "React & Vite" (it's Next.js 16), TRD says "React 18 + Vite + llama.cpp" (React 19 + Next 16 + transformers), AGENTS.md describes deleted files and an empty test suite (106 tests pass). One reconciliation pass + verify the Quickstart in CI. **Cost:** ~1 day. **Outcome:** a newcomer's first hour stops being spent correcting the docs by hand.

## S9 — Chat lifecycle states + first-run empty state
Five states in the store (no-model / loading / ready / generating / error), gate the input on them, add an OOM card, and give the home page a chat-first empty state with two CTAs: download a model / import a local GGUF. **Cost:** ~1-2 days. **Outcome:** the UI never silently does nothing; first-run users know exactly what to do next.

## S10 — Ship like a product: tags, a bundle, a changelog
No tags, no releases, no migration notes; `install.sh` clones main. Tag v1.0.0 (version is already hardcoded in config.py), pin the installer to the tag, publish the `setup_package.sh` artifact so first-run doesn't compile/pull a gigabyte, and start a CHANGELOG. **Cost:** ~1 day. **Outcome:** an upgrade path exists; the offline promise stops being contradicted by the installer.

## S11 — Repo hygiene and scope hygiene
Delete committed build/error artifacts (`frontend/ts_errors*.txt`, `build_output*.txt`, `electron/build_*_output.txt`, root debug scripts) and gitignore them; document the ownership of the `llama-cpp-tq/` sub-project and `landing_page/` (or extract them); verify whether `MemoryManager`'s zone bookkeeping is actually used before deleting it. **Cost:** ~1h. **Outcome:** the repo tells one story; contributors stop tripping over stale artifacts.
