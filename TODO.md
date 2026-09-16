# Backend TODO — Audit 2026-09-15

Audit scope: `backend/` (app, tests, benchmarks). Results from actually running checks, not reading docs.

## Status after fixes (2026-09-15, same day)

| # | Issue | Status |
|---|---|---|
| 1 | WS metrics KeyError + dead-client spam | ✅ **FIXED** |
| 2 | Bare `except: pass` in model_manager.py | ✅ **FIXED** |
| 3 | USB bundle signing stub | ✅ **IMPLEMENTED** (ed25519) |
| 4 | TurboQuant eval gate fails | ⏸ Open (deliberate, default-OFF) |
| 5 | TestClient broken / chat e2e uncovered | ✅ **FIXED** (claim was stale) |
| 6 | No linter | ✅ **ADDED** (ruff, config + clean) |
| 7 | `config/storage.toml` missing | ⏸ Won't-fix (documented) |
| 8 | `print()` in production paths | ✅ **FIXED** (all swapped to logger) |
| 9 | Silent `except Exception: pass` | ✅ Partial (kept where probe-and-fallback is correct) |
| 10 | Doc debt (Docs/, TRD.md) | ⏸ Open (out of backend scope) |

**Verification:** `ruff check app tests benchmarks` → clean · `pytest -m "not slow"` → 139 passed · `pytest -m slow` → 5 passed · compileall clean · signing self-check passes.

---

## 1. ✅ WebSocket metrics broadcast to dead clients — FIXED

**Evidence:** `server_err.log` — 50+ consecutive `socket.send() raised exception.` lines.
**File:** `backend/app/websocket/metrics.py`

- `clients.remove(websocket)` could raise `KeyError` (already discarded by `broadcast_metrics`) → replaced with `discard()`.
- Dead sockets now get an explicit `await client.close()` after a failed broadcast send so uvicorn stops retrying them.

## 2. ✅ Bare `except: pass` hides corruption — FIXED

**File:** `backend/app/services/model_manager.py:176`

`except: pass` → `except (OSError, json.JSONDecodeError, ValueError): pass`. No bare excepts remain in the codebase.

## 3. ✅ USB bundle signing implemented — ed25519

**File:** `backend/app/providers/usb_bundle.py` (was: `TODO: Implement actual signing` writing 64 zero bytes)

- Signing: ed25519 over `metadata_bytes + checksum_bytes` (checksum binds model data); 64-byte sigs match the existing bundle format exactly.
- Keys derive deterministically (`sha256("sovereign-sign:" + key)`) from the existing `encryption_key`/`verify_key` config — same trust root as bundle encryption, zero new key management.
- `# ponytail:` marker notes the ceiling: no per-bundle key rotation / separate signing key UI; add when enterprise distribution needs it.
- Verification happens in `_parse_sovereign_bundle` — every consumer (list, extract) routes through it. Bad signature or missing verify key → bundle refused (returns `None`, skipped by scan).
- Self-check: `backend/tests/usb_bundle_signing_check.py` — run with `PYTHONPATH=. python tests/usb_bundle_signing_check.py`. Covers: valid sig accepted, tampered payload refused, signed-without-key refused, unsigned still works.
- Skipped by design: no revocation lists, no external key files, no UI. Key derivation means signing and encryption share one secret — a dedicated signing key is the upgrade path if the trust model ever needs to split.

## 4. ⏸ TurboQuant eval gate still fails

`turboquant_enabled` defaults `False`. Gate (`benchmarks/accuracy_eval.py`) fails on Qwen2-0.5B + Pythia-70m (uniform centroids, not Beta Lloyd-Max; QJL decode ~0.98x). Do not re-enable until the gate passes.

## 5. ✅ TestClient works — AGENTS.md claim was stale

`TestClient(app)` constructs AND serves requests fine with starlette + httpx 0.28.1 (deprecation warning only: "install `httpx2` instead" — not blocking).

- Added `backend/tests/test_app_smoke.py` (imports app, serves `/`).
- **Gotcha:** do NOT use `with TestClient(app)` in tests — the context manager runs the real lifespan which touches `workspace/` DBs and pollutes other tests. Plain `TestClient(app)` = routes without lifespan.
- ✅ Chat HTTP e2e added: `backend/tests/test_chat_api_http.py` — fake engine wired into `app.state`, 5 fast tests covering OpenAI response shape, SSE framing/`[DONE]`, system-prompt injection, 400-no-engine, and engine-crash-mid-stream. Complements `test_chat_api_e2e.py` (@slow real model).
- Still uncovered: RAG (`vectorstore/` business logic beyond sync tests), `hardware_detector`, `settings/`, `websocket/`, `providers/`.

## 6. ✅ ruff added and enforced

`[tool.ruff]` in `backend/pyproject.toml`: `select = ["E4","E7","E9","F"]`, E402 ignored (late imports are the codebase's circular-import pattern), per-file ignores for `__init__.py` re-exports and test/benchmark locals.

- Fixed by hand: 3× F821 undefined-name `ModelManager` in `app/api/models.py` (missing import; annotation-only, but a latent crash if ever evaluated) and 5× F841 dead locals (fullram executor, layer_executor, vectorstore manager).
- Auto-fixed: 90 mechanical (56 unused imports, 15 empty f-strings, etc.).
- Remaining 0. `python -m ruff check app tests benchmarks` is now the cheap audit tool.

## 7. ⏸ Won't-fix: `config/storage.toml` referenced but missing

Referenced by `app/database/manager.py`, `app/vectorstore/config.py`, `app/vectorstore/manager.py` with correct fallback to `Settings` defaults. **Decision: keep the fallback, don't ship the file.** A repo-relative config would hardcode paths that fight the portability rule (runtime data lives in `./workspace/`, resolved from `Settings`, which is what the fallback already does). Delete the parameter only if the file is never coming.

## 8. ✅ print() → logger — FIXED

All production-path prints swapped to `logger.info/warning` with lazy `%s` formatting: `api/benchmark.py`, `core/hardware_llmfit.py`, `engines/layerstream/executor.py`, `splitter.py`, `layer_executor.py`, `shared/safetensors.py`, `providers/usb_bundle.py`. Only remaining prints: CLI (`app/cli/`, user-facing by design) and `__main__` self-checks.

## 9. ✅ Partial: silent except swallows

Left as-is where "probe and fall back" is the correct pattern (hardware detection probes, optional-dependency imports). The two that mattered — the bare except (#2) and the WS handler (#1) — are fixed. A blanket `logger.debug(exc_info=True)` pass over the remaining ~18 sites is mechanical but low-value; do it opportunistically.

## 10. ⏸ Doc debt (out of backend scope)

- `Docs/` duplicate wiki still references Vite.
- `Info_docs/project/TRD.md` still says React 18 + Vite (actual: Next.js 16 + React 19).

---

## Known flake — ROOT-CAUSED & FIXED

`tests/test_vectorstore_sync.py` failed ~1 in 3–6 full-suite runs with a *semantic* failure (search returned the wrong document), never a crash.

**Root cause:** `_FakeEmbedder._vec()` used Python's built-in `hash(word)` for bag-of-words slot placement. `str` hashing is **salted per process** (PYTHONHASHSEED), so word→slot mapping was random per pytest run. The self-heal test's query `"what do rockets need?"` shares zero exact tokens with the beta doc (punctuation: `rockets.` ≠ `rockets`), so its assertion passed only via random hash collisions — a coin flip per process.

**Fix (in the test file only):** `zlib.crc32` for stable slot placement + punctuation stripping in the fake embedder so intended token overlap actually exists. Verified: 12× pair loop (fresh hash salt each run) + 3× full suite, all green.

## Suggested next

1. Commit this state.
2. Chat e2e test with fake engine wired into `app.state` (now unblocked by #5).
3. Investigate the vectorstore flake when it bites CI (if CI exists by then — #6 made lint cheap, CI is the missing half).
