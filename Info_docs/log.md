# Wiki Log

## [2026-07-21] ingest | Initial Wiki Build
- Added wiki schema to CLAUDE.md (page format, operations, index/log conventions)
- Created index.md — catalog of all 31 wiki pages by category
- Created log.md — timeline tracking
- Batch-ingested 31 Docs/ sources into wiki pages with frontmatter, synthesis, and [[wikilinks]]
- Cross-linked related pages: PRD↔TRD, FullRAM↔LayerStream, tech-stack↔Technical Architecture, etc.
## [2026-07-23] implement | TurboQuant KV Cache Compression
- Created `backend/app/engines/shared/turboquant/` package (config, polarquant, qjl, codebook, kv_cache, hf_proxy)
- Added settings: `turboquant_enabled`, `turboquant_bits`, `turboquant_qjl_enabled`, `turboquant_rotation`
- Wired into LayerStream engine via optional `turboquant_config` param on `LayerExecutor`
- Added `KVCacheManager.create(mode="turboquant")` factory to layerstream/kv_cache.py
- Added `use_turboquant` flag to FullRAM `KVCache`
- Added `sovereign benchmark-turboquant` CLI command
- Self-check verifies PolarQuant + QJL reconstruction MSE < 0.02 on unit vectors
- Skipped bit-packing (ponytail) — add when real memory pressure is measured
