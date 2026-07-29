# Wiki Log

## [2026-07-21] ingest | Initial Wiki Build
- Added wiki schema to CLAUDE.md (page format, operations, index/log conventions)
- Created index.md — catalog of all 31 wiki pages by category

## [2026-07-23] implement | TurboQuant KV Cache Compression
- Created `backend/app/engines/shared/turboquant/` package (config, polarquant, qjl, codebook, kv_cache, hf_proxy)
- Added settings: `turboquant_enabled`, `turboquant_bits`, `turboquant_qjl_enabled`, `turboquant_rotation`
- Wired into LayerStream engine via optional `turboquant_config` param on `LayerExecutor`
- Added `KVCacheManager.create(mode="turboquant")` factory to layerstream/kv_cache.py
- Added `use_turboquant` flag to FullRAM `KVCache`
- Added `sovereign benchmark-turboquant` CLI command
- Self-check verifies PolarQuant + QJL reconstruction MSE < 0.02 on unit vectors
- Skipped bit-packing (ponytail) — add when real memory pressure is measured

## [2026-07-24] review | Ponytail Review
- Ran `/ponytail-review` across full codebase
- Found ~3800 lines of unnecessary complexity (dead providers, duplicate task resolvers, 1003-line inference handler with 18 unused task handlers, USB bundle protocol over-engineering, zombie memory manager, etc.)
- Created [[workflow/Ponytail Review|Ponytail Review]] page, updated index
- Created log.md — timeline tracking
- Batch-ingested 31 Docs/ sources into wiki pages with frontmatter, synthesis, and [[wikilinks]]
- Cross-linked related pages: PRD↔TRD, FullRAM↔LayerStream, tech-stack↔Technical Architecture, etc.

## [2026-07-24] ingest | Literature Review
- Created [[project/Literature Review|Literature Review]] — 6 high-impact papers on edge AI, quantization, attention, speculative decoding, RAG
- Cross-linked to FullRAM, LayerStream, Engine Algorithms
- Updated index, appended to log

## [2026-07-24] review | Ponytail Audit (full project)
- Scanned all backend (21,813 lines) + frontend (8,303 lines) + root
- Found ~5000 lines removable across USB bundle provider, enterprise repo, ManualStream, inference.py handlers, settings over-engineering, root clutter, singleton pattern, layerstream executor duplication
- Created [[workflow/Ponytail Audit|Ponytail Audit]] page, updated index, appended to log

## [2026-07-24] doc | Technical Documentation (.docx)
- Created `create_docs.py` — generates a professional `.docx` technical documentation file for SovereignAI Edge
- 12 sections covering executive summary, architecture, dual engines, UI, plugins, RAG, model management, API reference, setup, security, system requirements, project structure
- Styled output with cover page, table of contents, tables, code blocks, color headers
- Drops into `/sessions/.../SovereignAI_Edge_Documentation.docx`

## [2026-07-25] ingest | llmfit Integration Analysis
- Created [[tech-stack/llmfit|llmfit]] wiki page — hardware-aware model recommendation engine analysis
- 5 integration opportunities identified: replace HardwareDetector, add `/v1/models/recommend`, enhance engine selection, real benchmark integration, custom model catalog
- Updated index.md with llmfit entry under Tech Stack
- Cross-linked to HardwareDetector, ModelManager, EngineRouter, Provider pattern, Benchmark API
- Updated CLAUDE.md with skills-lock.json update

## [2026-07-26] implement | Ponytail Audit Cleanup & QA Review
- Removed ~841 lines of dead code: `fullram/loader.py`, `layerstream/eviction.py`, `layer_by_layer_inference.py`
- Refactored `security/encryption.py` (133 lines changed) — improved encryption implementation
- Cleaned up `main.py`, `huggingface.py`, `settings/service.py`, `websocket/metrics.py`
- Updated `layer_executor.py` with minor fix
- Fixed chat endpoint inconsistencies in `api/chat.py`
- Updated dependencies (`pyproject.toml`, `requirements.txt`), removed `test_dummy.py`
- Created QA review docs: `qa.md`, `QA_FIXES_REPORT.md`, `SECURITY_FIXES_REPORT.md`
- Updated `Sovereign.canvas` Obsidian knowledge graph visualization

## [2026-07-27] implement | GGUF Header Reader & BitNet/ik_llama.cpp Support
- Created `backend/_read_header.py` — standalone GGUF header parser (reads tensor info, metadata, quantization type from `.gguf` files without loading the full model)
- Added `_IkModelWrapper` and ik_llama.cpp fallback in `fullram/executor.py` — enables FullRAM engine to load BitNet b1.58 / IQ2_BN quantized models via `ik_llama.cpp` with graceful fallback to `llama_cpp`
- Patched GGUF quantization types in `main.py` — adds IQ2_BN (135) enum entry for older gguf PyPI packages lacking newer quant support
- Renamed `plugins/init.py` → `__init__.py` for proper Python package convention
- Cleaned up `settings/service.py` (removed unused import)

## [2026-07-27] doc | Architecture Diagrams
- Created `diagrams/sovereignai-architecture.mmd` — Mermaid architecture diagram covering data layer, API gateway, inference engines, plugin sandbox, RAG pipeline, hardware monitoring, CLI/Electron frontends
- Created `Info_docs/Excalidraw/SovereignAI.excalidraw.md` — Excalidraw visual architecture diagram with component relationships
- Updated `Info_docs/Sovereign.canvas` — refreshed Obsidian knowledge graph visualization

## [2026-07-28] implement | TurboQuant KV Cache Refactoring
- Refactored `turboquant/codebook.py` — simplified codebook logic (61 lines changed)
- Enhanced `turboquant/hf_proxy.py` — improved HF model proxy handling (22 lines added)
- Optimized `turboquant/kv_cache.py` — major KV cache refactoring (120 lines changed, +117/-86)

## [2026-07-28] ingest | Codebase Analysis with graphify
- Ran `/graphify` skill to analyze SovereignAI codebase structure (651 files, ~2.5M words)
- Generated interactive HTML visualization (`graphify-out/graph.html`)
- Created GraphRAG-ready JSON detection file (`.graphify_detect.json`)
- Produced audit report (`graphify-out/GRAPH_REPORT.md`)
- Added insights to project knowledge base

## [2026-07-28] doc | README and Knowledge Graph Updates
- Updated `readme.md` — minor cleanup and project overview improvements
- Updated `Info_docs/Sovereign.canvas` — refreshed Obsidian knowledge graph visualization
