# Code Review Report

**Date:** 2026-10-27
**Scope:** `main...HEAD` — commit `e9513a4b` *22/10/2026*
**Files changed:** 1 new file, `scripts/_probe.py` (9 lines)
**Working tree:** clean, `origin/master` in sync

---

## Summary

| Severity | Count |
|----------|-------|
| High | 1 |
| Medium | 3 |
| Low | 4 |

Single-file diff. No security issues (no input parsing, no network, no file writes). All findings concern
whether the probe actually serves a purpose: it is unreferenced by CI, prints but never verifies, and
misreports broken installs as missing.

Note: the reviewed file **is** worth keeping in some form. A dependency probe against
`backend/requirements.txt` pins is genuinely useful — the pins are load-bearing (see `httpx<0.28` comment at
`backend/requirements.txt:29` and the transformers version gate at `backend/app/engines/fullram/executor.py:79-86`).

---

## Findings

### 1. HIGH — Probe can never fail; unusable as a gate
**`scripts/_probe.py:9`**

Script returns exit status 0 unconditionally, even when every module is reported `MISSING`. `except` prints
and falls through; no error counter, no `sys.exit(1)`.

**Failure:** `python scripts/_probe.py` on a host without torch/faiss prints `torch MISSING ...` and exits 0.
Any `&&` chain, CI step, or `check_portable.sh` gate treats the environment as healthy and proceeds to a build
that fails later with an opaque import error.

---

### 2. MEDIUM — No interpreter identity in output
**`scripts/_probe.py:3`**

Prints `sys.version` but not `sys.executable`.

**Failure:** Developer runs `python scripts/_probe.py` from repo root with system Python instead of
`backend/.venv/Scripts/python.exe`. Every backend package shows `MISSING`. Nothing in the output identifies
which interpreter was probed, so the result is misdiagnosed as a broken venv.

---

### 3. MEDIUM — Module list omits the deps that actually break the app
**`scripts/_probe.py:4`**

Probed: `fastapi, starlette, httpx, aiohttp, certifi, huggingface_hub, cryptography, tqdm, torch`.

Missing, all pinned in `backend/requirements.txt`: `pydantic`, `transformers`, `uvicorn`, `aiosqlite`,
`numpy`, `gguf`, `faiss`, `sentence_transformers`. Probed but incidental: `certifi`, `tqdm`.

**Failure:** transformers drifts off the `==4.45.2` pin while fastapi/httpx/torch all match. Probe prints a
clean list. `executor.py:83` branches on `_transformers.__version__.split('.')[:2]` to choose the `dtype` vs
`torch_dtype` kwarg, so model load breaks while the probe reported healthy.

---

### 4. MEDIUM — Reports versions but cannot detect pin drift
**`scripts/_probe.py:7`**

Reads `mod.__version__`, never compares against `backend/requirements.txt`.

**Failure:** `fastapi==0.109.0` pinned, 0.115.0 installed — prints `fastapi 0.115.0` and exits fine. The
entire point of a dependency probe (pin conformance) goes unchecked; a human must diff two lists by eye.
The `httpx<0.28` constraint exists precisely because 0.28 removed the `app` kwarg `TestClient` uses — exactly
the kind of drift this can't catch.

---

### 5. LOW — `__import__` for a version number executes full import side effects
**`scripts/_probe.py:6`**

`importlib.metadata.version(m)` returns the same number without importing the module.

**Failure:** Probing `torch` imports the CUDA runtime (multi-second, hundreds of MB RSS, thread spawns). On a
host with a broken CUDA DLL it can fail for reasons unrelated to whether torch is installed.

---

### 6. LOW — `except Exception` conflates "not installed" with "installed but broken"
**`scripts/_probe.py:8`**

**Failure:** `cryptography` installed but its `_rust` extension fails to load (arch mismatch) → output reads
`cryptography MISSING No module named 'cryptography.hazmat.bindings._rust'`, sending the reader to
`pip install cryptography`, which is already satisfied and will not fix anything. Only `ModuleNotFoundError`
means MISSING; anything else is broken and the traceback is dropped entirely.

---

### 7. LOW — No docstring, no `__main__` guard
**`scripts/_probe.py:1`**

Sibling `scripts/release_lib.py` has both. Any tooling that imports files under `scripts/` (test discovery,
a future `__init__.py`, IDE introspection) triggers the probe body on import, including the multi-second
`import torch`.

---

### 8. LOW — Unreferenced by CI, build scripts, or docs
**`scripts/_probe.py:1`**

Grepping the repo for `_probe` finds no caller. Not wired into `.github/workflows/backend.yml`,
`scripts/check_portable.sh`, or any doc. Generic underscored name, no stated purpose.

**Failure:** File accumulates as dead weight; the next maintainer cannot tell whether it is a release gate or
a leftover scratch file, so it is neither maintained (the module list is already stale) nor removed.

---

## Recommended fix

Keep it, make it a gate. One file, ~20 lines, no new deps:

```python
#!/usr/bin/env python3
"""Check installed deps against backend/requirements.txt constraints."""
import importlib.metadata as md
import re
import sys
from pathlib import Path

SPEC = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]*\])?\s*([=<>!~]=?.*)$")

def ver(s):  # "0.28.0" -> (0, 28, 0); good enough for these pins
    return tuple(int(p) for p in re.findall(r"\d+", s)[:3])

def ok(got, spec):
    for op, ref in re.findall(r"(==|>=|<=|~=|!=|>|<)\s*([\w.]+)", spec):
        a, b = ver(got), ver(ref)
        a += (0,) * (3 - len(a)); b += (0,) * (3 - len(b))
        if not {"==": a == b, ">=": a >= b, "<=": a <= b, ">": a > b, "<": a < b,
                "!=": a != b, "~=": a[:2] == b[:2] and a >= b}[op]:
            return False
    return True

req = Path(__file__).resolve().parent.parent / "backend" / "requirements.txt"
pins = {}
for line in req.read_text(encoding="utf-8").splitlines():
    m = SPEC.match(line.split("#")[0].strip())
    if m:
        pins[m.group(1).lower()] = m.group(2)

print("python", sys.version.split()[0], sys.executable)
bad = 0
for pkg, spec in pins.items():
    try:
        got = md.version(pkg)
    except md.PackageNotFoundError:
        print(f"{pkg} MISSING (want {spec})")
        bad += 1
        continue
    if not ok(got, spec):
        print(f"{pkg} {got} violates {spec}")
        bad += 1
print("OK" if not bad else f"{bad} problem(s)")
sys.exit(1 if bad else 0)
```

Then wire it in: add `python scripts/_probe.py` (run with the venv interpreter) as a step in
`.github/workflows/backend.yml`, and rename the file to something descriptive (`check_deps.py`) since `_probe`
implies throwaway. Otherwise delete it — `python -m pip check` plus `pip list` covers the non-pin case.

→ skipped: hasn't been applied to the working tree; report only.
→ add when: you want it as a CI gate — that requires the `backend.yml` edit too.
