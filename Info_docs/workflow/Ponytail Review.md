---
tags: [code-review, ponytail, complexity]
source: "[[CLAUDE.md]]"
created: 2026-07-24
updated: 2026-07-24
---

# Ponytail Review: SovereignAI Edge

Scope: over-engineering and unnecessary complexity only. Not bugs, security, or performance.

## 1. Dual task type resolution (duplicated logic)

| File | Tag | What | Replacement |
|------|-----|------|-------------|
| `backend/app/core/task_resolver.py:L1-159` | delete | `TaskResolver` — 45+ if-elif branches mapping HuggingFace architectures. video_classification, depth_estimation, table_qa etc never used on edge platform | Use `ModelDetector` instead, delete this file |
| `backend/app/model_manager/detector.py:L1-245` | yagni | `_match_model_type` heuristic duplicates architecture mapping from `ARCHITECTURE_TASK_MAP` | Use suffix match only, delete `_match_model_type` |
| `backend/app/model_manager/config.py:L101-235` | yagni | `ARCHITECTURE_TASK_MAP` with 60+ entries (Bloom, Cohere, OPT, DebertaV2, YOLOS, DPT, Blip2, Llava). Edge GGUF platform hits CausalLM 99% | Keep only CausalLM + MaskedLM + Seq2SeqLM entries |
| `backend/app/core/task_router.py:L1-157` | delete | Imports 27+ AutoModel classes. `AutoModelForVideoClassification`, `AutoModelForAudioXVector`, `AutoModelForTextToWaveform` etc never loaded on edge | Delete entire file, fold into FullRAM engine directly |

## 2. Over-engineered provider system

| File | Tag | What | Replacement |
|------|-----|------|-------------|
| `backend/app/providers/base.py:L1-443` | yagni | `ModelMetadata` with 30+ fields, `DownloadProgress` with 10+ properties, 4 abstract methods with full docstrings. `to_dict()` boilerplate | `dataclass.asdict()` gives you `to_dict()` free |
| `backend/app/providers/exceptions.py:L1-179` | shrink | 8 exception classes with 40-line constructors each | One `ProviderError` with optional `provider` string |
| `backend/app/providers/usb_bundle.py:L1-1066` | yagni | 1066-line USB bundle provider. Custom binary format (magic bytes, version, flags, checksums, signatures, Fernet encryption), ZIP/TAR extraction, drive detection on 3 OSes, bundle creation | `shutil.copy2` from a mounted path covers 90%. Delete everything else |
| `backend/app/providers/enterprise_repo.py:L1-359` | yagni | Enterprise repo with 4 auth methods, health check pings, full search/download API | Offline edge platform. Delete until enterprise customer exists |

## 3. Bloated inference handler

| File | Tag | What | Replacement |
|------|-----|------|-------------|
| `backend/app/model_manager/inference.py:L1-1003` | yagni | 20+ handler methods for object_detection, semantic_seg, depth_estimation, ctc, text_to_waveform, multiple_choice, next_sentence, image_to_image | Edge runs GGUF → only `_causal_lm` and maybe `_text_encoding`. Delete 18 handlers |

## 4. Plugin sandbox that does nothing

| File | Tag | What | Replacement |
|------|-----|------|-------------|
| `backend/app/plugins/sandbox.py:L1-56` | delete | `_set_limits()` never called. `resource` import fails silently on Windows. `ThreadPoolExecutor` unused | Inline `asyncio.wait_for(plugin.execute(...), timeout)` in manager. Delete file |

## 5. Zombie memory manager

| File | Tag | What | Replacement |
|------|-----|------|-------------|
| `backend/app/core/memory_manager.py:L1-111` | delete | 4 zones (layer_buffer, prefetch_buffer, activation_buffer, kv_cache), lock-based allocation, `suggest_mode()`. Zero active callers from engines | Remove. Each engine manages its own memory |

## 6. Hand-rolled numpy ops (dead code)

| File | Tag | What | Replacement |
|------|-----|------|-------------|
| `backend/app/engines/shared/inference.py:L1-90` | delete | Hand-rolled softmax, attention, layer_norm, rms_norm, apply_rope in numpy | PyTorch handles all this internally. Dead code |

## 7. Hand-rolled sampling

| File | Tag | What | Replacement |
|------|-----|------|-------------|
| `backend/app/engines/layerstream/sampler.py:L1-36` | delete | Custom top-k/top-p/temperature sampler | `model.generate()` does this internally |

## 8. Custom audit system

| File | Tag | What | Replacement |
|------|-----|------|-------------|
| `backend/app/security/audit.py:L1-73` | stdlib | AuditLogger with severity levels, DB inserts, global singleton | `logging` module with file handler |

## 9. Empty / placeholder files

| File | Tag | What | Replacement |
|------|-----|------|-------------|
| `backend/app/security/license.py` | delete | Empty file | Nothing |
| `backend/app/database/models.py` | delete | Empty file | Nothing |
| `backend/app/engines/shared/init.py` | delete | Empty `__init__` in dead-code directory | Nothing |
| `backend/app/services/quantizer.py` | delete | Empty file | Nothing |

## 10. Download manager duplication

| File | Tag | What | Replacement |
|------|-----|------|-------------|
| `backend/app/services/downloader.py:L1-93` | delete | DownloadManager with resume, checksum, cache, active tracking. Duplicates `model_manager/downloader.py` | Use the one in model_manager |

## 11. Frontend settings exploded

| File | Tag | What | Replacement |
|------|-----|------|-------------|
| `frontend/components/settings/Setting.tsx` | delete | Contains comment/example, not actual component | Remove |
| `frontend/components/settings/` | shrink | 12+ settings component files (AgentCard, AgentSettings, CharacteristicChip, DataControlsSettings, GeneralSettings, etc) | 2-3 screens max |

## Summary

`net: -3800 lines possible.`

Blocks cut: ~2300 (providers), ~1000 (inference handlers), ~200 (task resolver duplicates), ~100 (sandbox), ~100 (core memory manager), ~100 (shared inference).
