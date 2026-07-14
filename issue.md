# Ponytail Review: SovereignAI Backend

## Over-Engineering Findings

### Duplicate Implementations (Critical)

**backend/app/engines/layerstream/executor.py:L18-L309** yagni: `LayerStreamEngine` (309 lines). Replacement: keep one engine.

**backend/app/engines/layerstream/eviction.py:L15-L267** yagni: SECOND `LayerStreamEngine` (267 lines) with placeholder implementations (`np.random.randn` for embeddings). Delete entirely.

**backend/app/engines/layerstream/layer_by_layer_inference.py:L245-L428** yagni: THIRD engine `LayerByLayerEngine` (184 lines) doing same layer-by-layer inference. Delete or merge.

**backend/app/engines/layerstream/introspection.py:L4-L84** yagni: `ModelIntrospector` (70 lines). Duplicate in `layer_by_layer_inference.py:L25-L84`. Keep one, delete other.

**backend/app/engines/layerstream/splitter.py:L9-L77** yagni: `WeightSplitter` (69 lines). Duplicate in `layer_by_layer_inference.py:L91-L133`. Keep one, delete other.

### Speculative Abstractions (YAGNI)

**backend/app/core/task_router.py:L43-L89** yagni: `TASK_CLASS_MAP` with 44 entries covering vision, audio, video, segmentation, detection, etc. Only `causal_lm` and `seq2seq_lm` are used. Replace with dict of 2 entries or `AutoModelForCausalLM` default.

**backend/app/engines/manualstream/executor.py:L14-L256** delete: `ManualStreamEngine` prototype (256 lines) with random tensor fallbacks. Not production code. Nothing replaces it.

**backend/app/engines/layerstream/scheduler.py:L9-L118** yagni: `LayerScheduler` + `LayerState` enum + `LayerInfo` dataclass (118 lines). Only used in deleted `eviction.py` engine. Replace with simple list/dict if needed.

**backend/app/engines/layerstream/prefetch.py:L9-L98** yagni: `PrefetchQueue` + `PrefetchTask` (98 lines). Only used in deleted `eviction.py` engine. Nothing replaces it.

**backend/app/engines/layerstream/mmap_loader.py** (not read but imported in eviction.py) yagni: `MMapLoader` - only used in deleted engine.

**backend/app/engines/fullram/kv_cache.py** (imported in eviction.py) yagni: `KVCache` - only used in deleted engine.

**backend/app/engines/shared/tokenizer.py:L8-L81** delete: Custom `Tokenizer` (81 lines) with regex word-splitting. `transformers.AutoTokenizer` exists. Replace with stdlib.

**backend/app/engines/fullram/loader.py:L8-L86** yagni: `GGUFLoader` (78 lines) hand-rolled GGUF parser. `transformers`/`llama.cpp` handle this. Replace with `AutoModelForCausalLM.from_pretrained(..., gguf_file=...)`.

### Stdlib/Native Replacements

**backend/app/engines/layerstream/layer_executor.py:L166-L185** stdlib: `inspect.signature(layer.forward)` called in hot loop per layer per token. Cache signature once in `__init__` or use `hasattr` checks.

**backend/app/engines/layerstream/kv_cache.py:L59-L148** shrink: `ProxyList` + `HFProxyCache` (90 lines) reimplementing `DynamicCache` interface. Use `transformers.DynamicCache` directly with CPU tensors.

**backend/app/engines/layerstream/kv_cache.py:L5-L57** shrink: `KVCacheManager` (53 lines) with 4 separate lists. Use single `list[tuple[K, V]]` or `DynamicCache`.

**backend/app/database/connection.py:L13-L105** shrink: `ConnectionPool` (93 lines) with thread-local storage. Use `sqlite3.connect(..., check_same_thread=False)` directly; SQLite handles connection per thread natively.

**backend/app/database/manager.py:L24-L148** yagni: `DatabaseManager` + 7 table classes (`ModelsTable`, `SessionsTable`, `HardwareTable`, `DocumentsTable`, `PluginsTable`, `AuditTable`, `MigrationRunner`). Over-abstracted for SQLite. Inline SQL or use `sqlite-utils` / `dataset`.

### Dead Code / Debug Artifacts

**backend/app/engines/layerstream/layer_executor.py:L123-L124, L196-L197** delete: `if hasattr(self, "DEBUG") and self.DEBUG:` debug prints in hot path. Remove.

**backend/app/engines/layerstream/loader.py:L26-L46** shrink: `LayerWeightLoader` with `ThreadPoolExecutor(max_workers=1)` + future + cache dict. `safetensors.torch.load_file` is fast enough; remove async prefetch complexity.

**backend/app/engines/layerstream/executor.py:L147-L151** delete: Race condition guard protecting against unloading during generation. If unload is not called concurrently, remove. If it is, use a lock.

### Duplicate Engine Interface

**backend/app/engines/base.py:L6-L49** yagni: `BaseEngine` ABC with 6 abstract methods. Only 2 engines (FullRAM, LayerStream) implement it. Inline the 2 implementations or use a simple protocol.

---

## Net Impact

**net: -1,800+ lines possible** (removing 2 duplicate engines, 1 prototype engine, speculative task map, dead schedulers/prefetchers, custom tokenizer, GGUF parser, over-abstracted DB layer, debug code, and redundant introspection/splitter)