# FIX-IT TODO — feed this to Claude Code, one phase at a time

## PHASE 0 — Guardrails (do first, always)
```
Read reviews/*.md and reviews/*.json before touching code.
Do not re-optimize anything marked DONE or REJECTED in perf-research-2026-08-11.md.
Do not touch TurboQuant code except the one item listed below.
Run full test suite before AND after every phase. Must stay green (112+ pass).
```

---

## PHASE 1 — Ship OpenAI-Compat Wedge (highest priority, lowest effort)
```
Goal: finish OpenAI-compatible server as primary product wedge. It's ~80% built.

1. Audit backend/api/openai_compat.py (or wherever it lives) against OpenAI spec:
   /v1/chat/completions, /v1/models, /v1/completions (if used).
2. Verify streaming (SSE) matches OpenAI delta format exactly — test with real
   OpenAI SDK client (openai-python) pointed at localhost.
3. Fix any field mismatches (id, object, created, model, choices[].delta, finish_reason).
4. Add missing error responses in OpenAI error shape (not FastAPI default).
5. Confirm test_openai_compat.py covers: non-stream completion, stream completion,
   model listing, invalid model error, invalid payload error. Add missing cases.
6. Document the endpoint (README + curl example + openai-python example).
Do not add new features beyond spec compliance. Ship what exists correctly.
```

---

## PHASE 2 — Close Critical Test Gaps (only the two that matter)
```
Goal: cover the two zero-coverage paths most likely to hide production bugs.

1. Write test_fullram_executor.py — real tiny model, load → generate → unload,
   assert no leaked memory/handles, assert fallback to LayerStream on simulated OOM.
2. Write test_chat_api_e2e.py — real tiny model through /v1/chat/completions
   end-to-end (not mocked), covering both FullRAM and LayerStream engine paths.
3. Do NOT write plugin sandbox / RAG / WS / frontend tests yet — explicitly out
   of scope for this phase.
Run suite, confirm new tests catch real bugs (like the rotary_emb crash pattern
found in test_layerstream_roundtrip.py). Fix any bugs found.
```

---

## PHASE 3 — Honest Docs & Claims (cheap, high trust value)
```
Goal: docs match measured reality, not aspirational GGUF/llama.cpp stack.

1. Reconcile SovereignAI_Edge_Documentation.docx and the (1).docx duplicate —
   pick ONE stack description: HuggingFace transformers/safetensors (the real
   implemented one), not GGUF/llama.cpp (the aspirational one). Delete/merge
   the other file.
2. Replace "70B+ on 8GB RAM" claim everywhere with measured claim:
   "3B-8B Q4 models on 8GB RAM" per benchmark-2026-08-14.md.
3. Add a Known Limitations section: LayerStream sub-1 tok/s on CPU today,
   GPU path blocked on Windows (no causal-conv1d wheel), TurboQuant parked
   (default-off, 4/4 eval gates failed).
4. Update Notion Startup OS page (append only, don't overwrite) with this
   phase's completion status.
```

---

## PHASE 4 — Security P1 (if not already done — check completed-2026-08-12-to-2026-08-15.md first)
```
Goal: confirm air-gap/privacy claims match implementation.

1. Verify backend binds to 127.0.0.1 by default, not 0.0.0.0.
2. Verify Bearer auth middleware (security/middleware.py) is enabled by default
   for any LAN-exposed mode, not opt-in.
3. Confirm no telemetry/outbound calls exist — grep for requests/httpx/fetch
   calls to non-localhost hosts, fail build if found.
Skip this phase entirely if completed-2026-08-12-to-2026-08-15.md shows it's
already done — don't redo verified work.
```

---

## PHASE 5 — LayerStream Perf (only after Phase 1-4 shipped, only if still relevant)
```
Goal: sub-1 tok/s is the known bottleneck. Do NOT attempt without a Linux CUDA
box or full CUDA Toolkit + VS Build Tools installed — GPU path is blocked
without this, confirmed in benchmark-2026-08-15 follow-up.

1. If infra available: build causal-conv1d, causal-conv1d-update, fla kernels,
   re-run benchmark_layerstream.py, compare against 0.40 tok/s CPU baseline.
2. If infra NOT available: stop here, do not attempt CPU-only optimization
   beyond what's already measured-rejected in perf-research-2026-08-11.md.
3. Optionally: implement weight quantization (Q4/Q8) per the earlier learnings
   as the single biggest win — but only as a separate scoped task with its
   own eval gate (perplexity check), same rigor as TurboQuant gates.
```

---

## DO NOT DO (explicit no-list, save yourself time)
```
- Do not touch TurboQuant beyond leaving it default-off and documented as parked.
- Do not re-run perf items marked REJECTED or N/A in section 3.1 of results doc.
- Do not build plugin sandboxing (v1.2 roadmap, not now).
- Do not build C++ desktop app until Phase 1-3 ship (breadth-before-validation
  risk flagged in autoplan P6).
- Do not attempt GPU kernel builds without confirmed Linux/CUDA infra access.
```

Run phases in order. Each phase = one Claude Code session, verify tests green before moving to next.
