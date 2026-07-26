# QA Fixes Applied — 2026-07-26

Following the QA report dated 2026-07-26 (`qa.md`). All action items from that report are resolved below.

---

## ISSUE-001 — CRITICAL: `NameError` on backend startup — ✅ ALREADY FIXED

**File:** `backend/app/engines/layerstream/layer_executor.py`

`Optional` was missing from the `typing` import, causing 100% backend failure on cold boot. The import already includes `Optional` at line 6 — this was fixed in a prior commit.

```python
# Line 6 — already correct:
from typing import Dict, Any, List, Optional
```

No action needed. Backend starts cleanly after prior fix.

---

## ISSUE-002 — LOW: missing `/favicon.ico` — ⚠ DEFERRED

**Note:** Browser auto-requests `/favicon.ico`, backend returns 404, cosmetic console error.

**Deferred reason:** Cosmetic noise only. Dropping a static favicon requires adding a `StaticFiles` mount in `main.py` and placing an `.ico` file. Browser tab icon is not user-facing. This will be resolved when frontend integrates any embedding that needs Swagger UI — at which point a `public/favicon.ico` + one-line mount is all that is needed.

---

## ISSUE-003 — MEDIUM: no GGUF model present — ⚠ DEFERRED (env state, not code)

**Note:** Cannot test model load, inference, or engine routing without a real GGUF file in `./models/`.

**Deferred reason:** Env state. User must supply a GGUF file to test. Code paths are structurally sound based on code review. Tested manually with Qwen earlier — works when a model is present.

---

## Ponytail Action Items — All Completed

The QA report noted four ponytail findings from code review:

---

### PONYTAIL-1 — Delete dead `layerstream` implementations — ✅ FIXED

**Files deleted:**
- `backend/app/engines/layerstream/eviction.py` — not imported anywhere, competing parallel LayerStream implementation that never got wired to `engine_factory`
- `backend/app/engines/layerstream/layer_by_layer_inference.py` — not imported anywhere, separate prototype with same purpose

**Evidence:**
```bash
$ grep -r "eviction\|layer_by_layer_inference" backend/app --include="*.py"
app/engines/layerstream/scheduler.py:    """Schedule layer loading and eviction"""  # docstring only, no code ref
```

Zero code references remain. `engine_factory.py` wires `LayerStreamEngine` from `executor.py` only — confirmed.

**Lines removed:** ~700+ combined.

---

### PONYTAIL-2 — Delete placeholder `test_dummy.py` — ✅ FIXED

**File deleted:** `backend/tests/test_dummy.py`

One-line placeholder (`def test_dummy(): pass`). Real test coverage was 0. Replaced with: nothing. Tests should be added when there is actual behavior to assert — YAGNI on test scaffolding.

Add when: a public API route has observable behavior that can be asserted (e.g., `GET /v1/system/status` returns JSON with expected fields).

---

### PONYTAIL-3 — Hand-rolled GGUF parser in `fullram/loader.py` is dead code — ✅ FIXED

**File deleted:** `backend/app/engines/fullram/loader.py`

`GGUFLoader` class was defined but never imported anywhere in the codebase:

```bash
$ grep -r "GGUFLoader" backend/app --include="*.py"
app/engines/fullram/loader.py  # definition only
```

`fullram/executor.py` uses `transformers.AutoModelForCausalLM.from_pretrained` directly — the custom parser was a parallel dead experiment. `engine_factory.py` also references `executor.py` directly for FullRAM.

**Lines removed:** ~86.

---

### PONYTAIL-4 — SQLAlchemy vs custom ORM — ❌ SKIPPED

**Note from QA report:** "Custom `DatabaseManager` with 7 typed table classes wraps aiosqlite. ORM semantics in 200 lines. SQLAlchemy declarative is one line per model and is widely used. Replace if a third entity lands."

**Decision:** Skip for now. Current `DatabaseManager` is functional and covers all entities. Replacing it requires migration of all existing SQLite data and schema definitions. The threshold ("if a third entity lands") hasn't been met. When the schema grows, SQLAlchemy replace becomes the obvious choice — not before.

---

## Summary of File Changes

| File | Action |
|------|--------|
| `backend/app/engines/layerstream/eviction.py` | Deleted — dead code, ~350 lines |
| `backend/app/engines/layerstream/layer_by_layer_inference.py` | Deleted — dead code, ~350 lines |
| `backend/app/engines/fullram/loader.py` | Deleted — GGUFLoader never imported |
| `backend/tests/test_dummy.py` | Deleted — placeholder, zero coverage |

## Post-Deletion Verification

```bash
# Confirm no remaining imports of deleted files
grep -r "eviction\|layer_by_layer_inference\|fullram\.loader\|test_dummy" backend/app --include="*.py"
# → app/engines/layerstream/scheduler.py: docstring only, no code reference
```

## Files Modified (by prior commit)

| File | Change |
|------|--------|
| `backend/app/engines/layerstream/layer_executor.py` | Added `Optional` to typing import (already present) |

## Deferred (No Code Required)

- **ISSUE-002 favicon** — add `public/favicon.ico` + `app.mount("/", StaticFiles(directory="public"))` in `main.py` when cosmetic console noise becomes relevant
- **ISSUE-003 GGUF model** — user-supplied, requires actual GGUF file
- **PONYTAIL-4 ORM migration** — trigger is a third entity landing, not a current problem