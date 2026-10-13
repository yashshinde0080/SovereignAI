# CHANGES

## 2026-10-13 — release-readiness audit
- **Security:** `SettingsService.verify_password()` now fails closed when
  `password_hash` is absent, `None`, or malformed, instead of raising. This
  surfaced as an HTTP 500 from `POST /v1/settings/security/verify-password`
  whenever `require_password` was enabled without a password set. +4 regression
  tests (`backend/tests/test_settings_behavior.py`).
- **Dependencies (frontend):** `next` 16.1.6 -> 16.4.0 (non-breaking), clearing
  the critical Next.js advisory. `npm audit --omit=dev`: 8 vulns (1 critical,
  4 high) -> 4 (0 critical, 1 high, build-time only). Lockfile regenerated and
  verified with a clean `npm ci` + `npm run build`.
- **Tests (frontend):** `npm test` ran only `lib/maskedLm.test.ts` (6 of 17
  tests), silently skipping 2 of 3 test files. It now runs
  `node --test "lib/*.test.ts"` (17/17).
- **CI lint gate:** `ruff check app tests benchmarks` — the exact command
  `backend.yml` runs — was failing on the default branch (unused `import json`
  in `backend/app/settings/service.py`). Removed; the gate now passes.
- **CI:** added `.github/workflows/frontend.yml` (lint + unit tests + static
  export). The frontend previously had no automated checks; only `backend/**`
  and release builds ran in CI.
- **System page (Windows):** `HardwareDetector` hard-coded AVX2/AVX-512 as
  unsupported and returned `disk_type: "Unknown"` on Windows, so the System tab
  showed wrong CPU and Storage details. AVX flags now come from numpy's CPU
  feature table; disk type comes from a `Get-PhysicalDisk` probe cached in
  `.hw_cache.json` (runs once per machine, then ~free). +5 regression tests
  (`backend/tests/test_hardware_detector.py`).
- **Docs:** added `backend/.env.example` and a Configuration section in the
  README; corrected the Node.js prerequisite (18+ -> 20.9+ to build, 23+ to run
  the `.ts` unit tests) and the stale backend test counts in `AGENTS.md`.

## 2026-09-05
- CLI UI improvements (backend/app/cli/main.py):
  - Welcome panel on `sovereign` with no args
  - Spinners during model loading and server startup
  - Consistent error panels for all connection/HTTP errors
  - Polished chat TUI: double-bordered help, visual separators
  - All error messages use Panel/Panel.fit with colored borders
