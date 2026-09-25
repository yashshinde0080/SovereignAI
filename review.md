# Over-engineering review — SovereignAI Edge

Scope: complexity only. Correctness bugs, security and performance are out of
scope (several were found and fixed separately this session). Findings are
ranked biggest cut first. **Nothing here has been applied** — this is a list.

Two things to read first:

- An earlier pass in this session already applied the *code-quality* fixes you
  asked for (audit facade, inference gate, vector-store dedup, downloader,
  naming, turboquant guardrails). This review covers what is still standing,
  **including a self-review of that diff** in section A.
- Many findings below are file/asset deletions. You told me not to delete files,
  so I have not. They are listed because this is an honest complexity review;
  section A is the subset that is pure code-level cutting.

---

## A. Self-review of this session's diff (614 insertions, 463 deletions)

My own diff, held to the same standard. This is the part most worth acting on
because it is uncommitted.

`backend/app/api/chat.py:L203-206`: `stdlib:` hand-rolled 4-line `_null_slot()` async context manager. `contextlib.nullcontext()` already supports `async with` on Python 3.10+ (the stated floor in AGENTS.md). `-4`.
`backend/app/services/downloader.py:L61`: `yagni:` `timeout: aiohttp.ClientTimeout = _TIMEOUT` constructor parameter. No caller passes it; the module-level constant is the only value ever used. `-1`.
`backend/app/services/downloader.py:L45`: `yagni:` `_UNSAFE_NAME` regex plus three separate guards in `_safe_filename`. `Path(name).name != name` alone rejects `/`, `\` and `..`; the regex is belt-and-braces on a 12-line function. `-3`.
`backend/app/core/scheduler.py:L60-74`: `delete:` `get_stats()` returns a dict no caller reads (not even the tests). `get_queue_size()`/`get_active_count()` exist only to be asserted on in `test_scheduler_and_audit.py`; fold them together or delete. `-11`.
`backend/app/security/audit.py:L75-85`: `yagni:` `get_logs()` — one consumer, and that consumer is the test written alongside it. `AuditTable.get_recent`/`get_by_severity` already do this and already have an API surface. `-11`.
`backend/app/vectorstore/index.py` (11 lines) + `backend/app/vectorstore/embedder.py` (13 lines): `yagni:` two re-export shim modules. They exist because the files were empty and you asked me not to delete them — but a shim is *worse* than an empty file, because now `FAISSIndexBuilder` has two import paths. Correct fix is to rename `index_builder.py` → `index.py` and `embedding_pipeline.py` → `embedder.py`. `-24` (net `-0` after rename, but one name instead of two).
`backend/app/security/license.py:L16-30`: `delete:` `LicenseManager` — a class whose `__init__` raises and whose only method is unreachable by design. The 12-line module docstring carries all the information. `-24`.
`backend/app/services/quantizer.py:L16-22`: `delete:` `Quantizer` — same pattern, raises in `__init__`, no caller. Docstring is the value. `-16`.
`backend/app/utils/__init__.py:L1-12`: `shrink:` 12-line docstring explaining that the package is empty. `"""Intentionally empty — see app.config.Settings and app.main._configure_logging."""` `-9`.
`backend/tests/test_scheduler_and_audit.py:L105-106,L117-119`: `shrink:` asserts on accessors that only exist for these asserts. Test the behaviour (serialization, release-on-error), not the counters. `-8`.

Section A subtotal: **~-110 lines**, and it removes one duplicated import path.

---

## B. Project-wide, biggest first

`engine/` (27 files, 3,752 lines incl. its own `pyproject.toml`, CLI and 9-file test suite): `delete:` a complete second numpy GGUF inference engine — config/gguf/loader/model/inference/tokenizer/kv_cache/memory/utils — duplicating FullRAM + LayerStream + `engines/shared/tokenizer.py`. Zero references from backend, frontend, electron or landing_page. `-3752`.
`Docs/` (34 files, 2,577 lines): `delete:` 26 of 34 files share names with `Info_docs/` counterparts; AGENTS.md already calls this tree stale. `Info_docs/` is authoritative. `-2577`.
Root doc sprawl (3,294 lines): `delete:` `PIPELINES.md` (1303), `TECHNICAL_REPORT.md` (759), `research-results.md` (419), `TRD.md` (242), `algorithms-and-formulas.md` (210), `PRD.md` (182), `TODO.md` (103), `BENCHMARK_REPORT.md` (67), `CHANGES.md` (9). `Info_docs/` + `reviews/` already hold these. `-3294`.
Hand-maintained API references (1,638 lines): `native:` `sovereign_ai_postman_collection.json` (1337), `api_endpoints_curl.txt` (286), `commands.txt` (15, and stale — prescribes `pnpm` in an npm-only repo). FastAPI serves `/docs` and `/openapi.json` from the live routes. `-1638`.
`Diagrams/` (12 files, 597 lines): `delete:` duplicates the `Diagram/` folder (5 files). Two diagram trees for one subject. `-597`.
`backend/benchmark_{fullram,layerstream,llamacpp}.py` (268 lines): `yagni:` three loose scripts at `backend/` root duplicating the `backend/benchmarks/` package. Only reference is a comment in `memory_manager.py`. `-268`.
`backend/app/services/registry.py` (201 lines): `yagni:` a second model registry over the same `models` table. `ModelsTable` now reads both schemas, but `ModelRegistry` still owns `CREATE TABLE`/`ALTER TABLE` and a `models_legacy_v0` rename dance. Two writers, one table. `-201` (needs the schema decision).
`backend/app/engines/shared/turboquant/config.py:L30` + `kv_cache.py:L151-254`: `yagni:` two quantizer schemes where the shipped default is the known-worse one. The class docstring itself says affine measured "5-28x lower real-data NMSE than polar at the same bit rate", yet `quant_scheme` defaults to `"polar"`. The polar path (`codebook.py`, `qjl.py`, `polarquant.py` and its branches) is the experimental one. `-250`.
`backend/app/vectorstore/retriever.py:L19-167`: `yagni:` a 167-line `Retriever` class with one caller (`VectorStoreManager.build_context`) wrapping four collaborators the manager already owns and passes in. `-167`.
`backend/app/providers/usb_bundle.py` (1,111 lines): `yagni:` one provider is 2.4x the size of `huggingface.py` (723) and 2.4x `local.py` (460), including its own key-derivation/signing (`_sign_key` L114, `_verify_key` L122, `_sign_payload` L131) when `app/security/encryption.py` already owns Fernet+PBKDF2. Worth a targeted read; not measured here.
`backend/app/api/chat.py:L332-350`: `yagni:` `build_prompt()` is a fallback for when `tokenizer.apply_chat_template` is missing. Every local model path loads a real tokenizer; the cloud path consumes structured messages and never reaches it. `-15`.
`frontend/` 6 task modules: **not a finding — see section C.**
`landing_page/public/frames/` (240 JPEGs, ~12 MB): `native:` a scroll-scrub sequence hand-rolled as 240 separate decoded images. One HTML5 `<video>` + `currentTime` is the platform feature for this. `-239 files`.
`landing_page/rename-frames.js` + `src/app/api/rename-frames/route.ts` (60 lines): `delete:` a dev-time frame renamer shipped inside the marketing site, including a Next.js route handler that exists only to rewrite local filenames. `-60`.
`start_backend.bat` / `start_web.bat` / `start_electron.bat` (10 lines): `delete:` fully subsumed by `launch.bat`/`launch.sh`/`sovereign.bat`, and each hardcodes `D:\SovereignAI\...`, which violates the repo's own no-absolute-paths rule. `-10`.
`.graphify_detect.json`: `delete:` stale tool artifact whose contents are a file list of `debug_*.py` scripts that AGENTS.md says were already deleted. `-1`.
`backend/app/settings/defaults.py` (272) + `schemas.py` (217): `yagni:` `Pydantic` models plus a parallel defaults module for 6 settings sections. Not measured; flagging because the pair is ~490 lines for config that is read as a JSON blob per section anyway.

Section B subtotal: **~-12,800 lines**, plus one duplicated package and one duplicated diagram tree.

---

## C. Checked and explicitly NOT over-engineered

Recorded so this list is not actioned blindly. Two of my earlier findings were
plainly wrong and are corrected here:

- `backend/app/engines/layerstream/benchmark.py`: **alive.** `BenchmarkTracker` is constructed by `LayerExecutor` (L80) and records layer loads, compute, VRAM and KV size (L330-468). My earlier "dead" claim came from grepping dotted module paths and missing `from .benchmark`.
- `frontend/components/task/*`: **parked on purpose.** `TaskRouter.TASK_CLASS_MAP` maps only `causal_lm`/`seq2seq_lm`/`vision2seq` and raises for everything else; `FullRAMEngine` states "the QA/masked_lm decode branches are gone". `components/task/README.md` documents the intent. Wiring those UIs would advertise features no engine can run. `lib/maskedLm.ts` + its test are correctly retained.
- `backend/app/providers/` (`base.py` + 4 real implementers): one ABC with 4 genuine products, not a single-implementation interface.
- `backend/app/database/*_table.py`: 6 classes, 6 distinct tables.
- `backend/app/settings/`, `backend/app/engines/cloud/`, `backend/app/api/router.py`: 5 settings concerns, 5 provider types, 9 live subrouters.
- `backend/app/engines/shared/turboquant/` as a *module*: default-off and gate-failing, but deliberately quarantined behind `turboquant_enabled=False` with a startup warning. Removing it is a product decision, not a complexity one; only the duplicate polar default (section B) is a complexity finding.
- `backend/app/vectorstore/{chunker,index_builder,store,embedding_pipeline}.py`: each does a distinct job; only `retriever.py` is a layer with one caller.
- `backend/tests/test_scheduler_and_audit.py` and `test_model_registry_migration.py`: smoke/regression coverage is the ponytail minimum, not bloat.

---

## D. Correction to note

`backend/app/database/models_table.py`: `count()` and `get_total_storage_bytes()`
previously caught `sqlite3.OperationalError` and returned `0`, so
`DatabaseManager.get_stats()` permanently reported an empty model registry. That
was a bug, not over-engineering, and is fixed. The test that *asserted* the
zero (`test_modelstable_degrades_on_registry_schema`) was replaced.

---

## Ranked shortlist, if you only do five

1. `engine/` — 3,752 lines, one package, zero callers. (`-3752`)
2. `Docs/` + root doc sprawl — 5,871 lines of duplicated documentation. (`-5871`)
3. The three API-reference artifacts — 1,638 lines the framework already generates. (`-1638`)
4. `Diagrams/` + benchmark scripts + launcher scripts — 875 lines of duplication. (`-875`)
5. Section A, my own diff — ~110 lines, and it collapses a duplicated import path. (`-110`)

---

net: **~-12,900 lines possible**, ~-1 package (`engine/`), ~-1 duplicated diagram tree.

---

Review only. No file was deleted, moved or edited to produce this list.
