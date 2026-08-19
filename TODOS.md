# SovereignAI Python Engine — Clean Rewrite

## Overview

Replace the current scattered Python engines with a clean, self-contained
inference package. Modular, production-quality, minimal dependencies
(Python stdlib + numpy + safetensors). Supports loading large checkpoints
via memory-mapped access, configurable memory budgets, KV-cache inference,
and a proper CLI with timing/stats.

Location: `engine/` at repo root. Standalone package, importable or CLI.

---

## Architecture

```
engine/
├── __init__.py            # Public API: load(), generate(), Engine class
├── gguf.py                # GGUF binary format parser (header, tensors, metadata)
├── tokenizer.py           # BPE tokenizer (merges.txt + vocab.json)
├── model.py               # Transformer model: config, weights, forward pass
├── loader.py              # Memory-mapped checkpoint loader with budget control
├── kv_cache.py            # KV-cache for autoregressive generation
├── sampler.py             # Temperature, top-p, top-k sampling
├── inference.py           # Generation loop: prefill + decode with streaming
├── memory.py              # Memory budget manager (track usage, evict layers)
├── cli.py                 # CLI entry point (argparse-based)
├── config.py              # Config dataclass + JSON loader
├── utils.py               # Shared helpers (timing, memory stats, tensor ops)
├── tests/
│   ├── __init__.py
│   ├── test_tokenizer.py  # Encode/decode round-trip, edge cases
│   ├── test_config.py     # Config loading, defaults, overrides
│   ├── test_gguf.py       # GGUF parsing, tensor shapes
│   ├── test_loader.py     # Memory-mapped loading, budget enforcement
│   ├── test_inference.py  # Deterministic generation, EOS handling
│   ├── test_consistency.py # Output identical across memory budgets
│   └── conftest.py        # Shared fixtures (tiny model path, temp dirs)
├── examples/
│   ├── README.md          # Usage examples and sample outputs
│   ├── run_small.sh       # 256MB budget, streaming
│   ├── run_medium.sh      # 1GB budget
│   └── run_full.sh        # Unlimited (all in memory)
└── pyproject.toml         # Package metadata, deps, entry points
```

---

## Existing Code to Reuse

| What | Where now | What to take |
|------|-----------|--------------|
| BaseEngine ABC pattern | `backend/app/engines/base.py` | Interface shape (load/generate/stats) |
| LayerStream executor | `backend/app/engines/layerstream/executor.py` | Prefill→decode loop, `_stream_delta` |
| LayerWeightLoader | `backend/app/engines/layerstream/loader.py` | LRU cache budget logic, prefetch pattern |
| WeightSplitter quant | `backend/app/engines/layerstream/splitter.py` | int4/int8 dequant math |
| Sampler | `backend/app/engines/layerstream/sampler.py` | Top-K + Top-P + multinomial |
| MMapLoader (stub) | `backend/app/engines/layerstream/mmap_loader.py` | GGUF header parsing skeleton |
| Config reading | `backend/app/config.py` | Settings pattern |
| Model introspection | `backend/app/engines/layerstream/introspection.py` | Component detection |

**NOT reusing:** transformers dependency, PyTorch model loading, async/event-loop
patterns (the new engine is synchronous + optional async wrapper), FastAPI coupling.

---

## PHASE 1 — Foundation: GGUF Parser + Tokenizer + Config

### 1.1 GGUF Parser (`gguf.py`)

Parse the GGUF binary format (v3):
- Header: magic `0x46554747`, version, tensor_count, kv_count
- KV metadata: key (string) + type tag + value
- Tensor descriptors: name, ndims, dims[], quant_type, offset
- Alignment padding
- Tensor data region (mmap'd, not copied)

```python
class GGUFParser:
    def __init__(self, path: str):
        self.path = path
        self.header: dict = {}         # GGUF metadata KV pairs
        self.tensors: list[TensorInfo] = []  # name, shape, dtype, offset
        self._mmap = None              # mmap.mmap for data access

    def load(self) -> None: ...
    def get_tensor(self, name: str) -> np.ndarray: ...  # lazy, from mmap
    def get_metadata(self) -> dict: ...
    def close(self) -> None: ...
```

Support: F32, F16 initially. Q4_0, Q8_0 in Phase 5.

### 1.2 BPE Tokenizer (`tokenizer.py`)

Real BPE from HuggingFace format:
- `vocab.json` → token string → id mapping
- `merges.txt` → priority-ordered merge pairs
- Pre-tokenization regex (GPT-2 style: `'s|'t|'re|'ve|'m|'ll|'d| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+`)

Replace the stub in `backend/app/engines/shared/tokenizer.py`.

```python
class Tokenizer:
    def __init__(self, model_dir: str): ...
    def encode(self, text: str) -> list[int]: ...
    def decode(self, ids: list[int]) -> str: ...
    @property
    def vocab_size(self) -> int: ...
    @property
    def eos_token_id(self) -> int: ...
    @property
    def bos_token_id(self) -> int: ...
```

### 1.3 Config (`config.py`)

Dataclass loading from `config.json` or GGUF metadata:
```python
@dataclass
class ModelConfig:
    vocab_size: int
    n_layers: int
    n_heads: int
    n_kv_heads: int       # for grouped-query attention
    dim: int
    hidden_dim: int
    norm_eps: float = 1e-5
    rope_theta: float = 10000.0
    max_position_embeddings: int = 2048
```

### 1.4 Self-check

```python
def demo():
    """Verify tokenizer encode/decode round-trip."""
    # encode("hello world") → decode back → "hello world"
    # Known token IDs for known strings
    print("phase 1: PASS")
```

---

## PHASE 2 — Loader + Memory Manager

### 2.1 Memory-Mapped Loader (`loader.py`)

Load model weights from GGUF via mmap. Only touch pages when needed.

```python
class CheckpointLoader:
    def __init__(self, gguf_path: str, budget_mb: float = 0):
        """
        budget_mb=0 → unlimited (all in memory)
        budget_mb>0 → stream layers, keep only budget-worth in RAM
        """
        self.parser = GGUFParser(gguf_path)
        self.budget_bytes = int(budget_mb * 1024 * 1024) if budget_mb > 0 else 0
        self._loaded_tensors: dict[str, np.ndarray] = {}
        self._layer_lru: dict[str, float] = {}  # name → access time

    def load_tensor(self, name: str) -> np.ndarray:
        """Load a tensor. If budget allows, cache it. Otherwise return from mmap."""
        ...

    def evict(self) -> None:
        """Evict LRU tensors until under budget."""
        ...

    def stats(self) -> dict:
        """Return {loaded_mb, budget_mb, n_cached, n_evicted}."""
        ...
```

Key: reuse the LRU + budget eviction logic from
`backend/app/engines/layerstream/loader.py:LayerWeightLoader._enforce_budget()`.

### 2.2 Memory Budget Manager (`memory.py`)

Track per-component memory usage:
- Embedding: always resident
- LM head: always resident (often tied to embed)
- Norms: always resident (tiny)
- Layer weights: budgeted, evictable
- KV cache: budgeted, evictable

```python
class MemoryManager:
    def __init__(self, budget_mb: float = 0):
        self.budget_bytes = int(budget_mb * 1024 * 1024) if budget_mb > 0 else float('inf')
        self.reserved_bytes = 0    # embed + lm_head + norms
        self.layer_bytes = 0       # current layer weights
        self.kv_bytes = 0          # KV cache
        self.peak_bytes = 0        # high-water mark

    def track(self, component: str, size_bytes: int) -> None: ...
    def can_fit(self, size_bytes: int) -> bool: ...
    def usage(self) -> dict: ...
```

---

## PHASE 3 — Model + KV-Cache + Inference

### 3.1 Transformer Model (`model.py`)

Pure-numpy transformer forward pass. No PyTorch.

```python
class TransformerModel:
    def __init__(self, config: ModelConfig, loader: CheckpointLoader):
        self.config = config
        self.loader = loader
        # Load embed + lm_head + norms immediately
        # Layer weights loaded on-demand via loader

    def forward(self, token_ids: np.ndarray, kv_cache: KVCache | None = None) -> np.ndarray:
        """Run one forward pass. Returns logits [seq_len, vocab_size]."""
        # 1. Embed tokens
        # 2. For each layer: attention + FFN (load layer weights, compute, evict)
        # 3. Final norm → lm_head → logits
        ...
```

Core ops in `utils.py` (all numpy, no PyTorch):
- `matmul(a, b)` — np.matmul
- `rmsnorm(x, w)` — x / sqrt(mean(x²) + eps) * w
- `rope(q, k, pos, theta)` — rotary position embedding
- `softmax(x)` — np.exp(x - max) / sum
- `silu(x)` — x * sigmoid(x)
- `silu_gate(gate, up)` — elementwise gate * up

### 3.2 KV-Cache (`kv_cache.py`)

Cache key/value tensors across decode steps to avoid recomputation.

```python
class KVCache:
    def __init__(self, n_layers: int, n_heads: int, head_dim: int,
                 max_seq_len: int = 2048):
        self.k = np.zeros((n_layers, max_seq_len, n_heads, head_dim), dtype=np.float32)
        self.v = np.zeros((n_layers, max_seq_len, n_heads, head_dim), dtype=np.float32)
        self.cur_len = 0

    def append(self, layer_idx: int, k: np.ndarray, v: np.ndarray) -> None:
        """Append new k/v for one layer at current position."""
        ...

    def get(self, layer_idx: int) -> tuple[np.ndarray, np.ndarray]:
        """Get full k/v for one layer (all positions up to cur_len)."""
        ...

    @property
    def size_bytes(self) -> int:
        """Current memory usage of the cache."""
        ...
```

### 3.3 Sampler (`sampler.py`)

```python
def sample(logits: np.ndarray, temperature: float = 0.7,
           top_p: float = 0.9, top_k: int = 0) -> int:
    """Sample one token from logits. temperature=0 → greedy."""
    ...
```

Reuse logic from `backend/app/engines/layerstream/sampler.py:Sampler.sample()`.

### 3.4 Inference Loop (`inference.py`)

```python
def generate(model: TransformerModel, tokenizer: Tokenizer,
             prompt: str, max_tokens: int = 128,
             temperature: float = 0.7, top_p: float = 0.9) -> GenerationResult:
    """
    Generate text from prompt.
    Returns: GenerationResult(text, token_ids, stats)
    """
    # 1. Tokenize prompt
    # 2. Prefill: run all prompt tokens through model (fills KV cache)
    # 3. Decode: generate one token at a time using KV cache
    # 4. Stop at EOS or max_tokens
    ...

@dataclass
class GenerationResult:
    text: str
    token_ids: list[int]
    n_prompt_tokens: int
    n_generated_tokens: int
    elapsed_s: float
    tokens_per_second: float
    peak_rss_mb: float
    kv_cache_mb: float
```

---

## PHASE 4 — CLI + Examples + Docs

### 4.1 CLI (`cli.py`)

```bash
# Basic generation
python -m engine.cli run model.gguf -p "Hello, world" -n 128

# With memory budget
python -m engine.cli run model.gguf -p "What is 2+2?" --budget 512

# Verbose (per-layer timing)
python -m engine.cli run model.gguf -p "Explain gravity" --verbose

# Stats-only (load + print, no generation)
python -m engine.cli info model.gguf

# JSON output
python -m engine.cli run model.gguf -p "Hello" --json
```

Output:
```
> Hello, world! How can I help you today?

[tokens: 12 | time: 0.834s | tok/s: 14.4 | peak RSS: 487MB | budget: 512MB]
```

Subcommands:
- `run <model> -p <prompt>` — generate text
- `info <model>` — print model config, tensor count, size
- `bench <model>` — run benchmark at multiple budgets, print comparison table

### 4.2 Example Commands

```bash
# examples/run_small.sh
python -m engine.cli run models/tinyllama-1.1B.gguf \
    -p "The capital of France is" -n 64 --budget 256

# examples/run_medium.sh
python -m engine.cli run models/phi-2.gguf \
    -p "Write a haiku about programming" -n 128 --budget 1024

# examples/run_full.sh
python -m engine.cli run models/tinyllama-1.1B.gguf \
    -p "Once upon a time" -n 256
```

### 4.3 Documentation

`examples/README.md`:
- Installation: `pip install -e engine/`
- Quick start
- Memory budget guide (how to pick budget for your model)
- Troubleshooting

---

## PHASE 5 — Test Suite

### 5.1 Core Invariant

**Same model + same prompt + same temperature=0 = same output regardless of memory budget.**

Proves memory management doesn't corrupt state or lose precision.

### 5.2 Test Cases

| Test | What it proves |
|------|----------------|
| `test_tokenizer_encode_decode_roundtrip` | encode→decode preserves text |
| `test_tokenizer_unknown_token` | handles out-of-vocab gracefully |
| `test_config_defaults` | missing fields get sensible defaults |
| `test_config_from_json` | JSON config loaded correctly |
| `test_gguf_parse_header` | header, tensor count, metadata extracted |
| `test_gguf_tensor_shape` | tensor shapes match config |
| `test_loader_budget_enforced` | peak RSS ≤ budget + margin |
| `test_loader_lru_eviction` | oldest layer evicted first |
| `test_generation_deterministic` | temp=0, same seed → same tokens |
| `test_generation_eos_stops` | stops at EOS token |
| `test_generation_empty_prompt` | edge case: empty string |
| `test_generation_long_prompt` | truncates at max_position_embeddings |
| `test_consistency_across_budgets` | **key test**: output identical at 256MB vs unlimited |
| `test_memory_tracking` | stats report correct usage |
| `test_kv_cache_grows` | cache size grows with sequence length |

### 5.3 Run

```bash
cd engine
python -m pytest tests/ -v                    # all tests
python -m pytest tests/test_consistency.py -v  # budget consistency only
python -m pytest tests/ -v --tb=short          # quick feedback
```

Use a tiny model fixture (e.g., synthetic 2-layer transformer or a small
GGUF like `tinyllama-1.1B-q4`) for fast test runs. Mark slow tests with
`@pytest.mark.slow` for CI.

---

## PHASE 6 — Quantization Support (deferred)

Support Q4_0 and Q8_0 dequant in the loader:
- Q8_0: 32 values/block, fp32 scale, int8 indices
- Q4_0: 32 values/block, fp16 scale, packed int4 nibbles

Dequantize to F32 on load (not stored in cache in compressed form — numpy
can't do matmul on int8). The savings come from *not loading* layers until
needed, not from storing compressed.

---

## ponytail Decisions

- **numpy only, no PyTorch.** numpy is the lazy choice — already installed
  everywhere, no CUDA complexity, `np.matmul` is BLAS-backed (fast).
- **No async/generator API in v1.** Synchronous generate(). Async wrapper
  is one `asyncio.to_thread` call if someone needs it later.
- **No safetensors dependency.** GGUF is the target format. safetensors
  support is a one-file addition if needed.
- **argparse, not click/typer.** Stdlib. No extra dep. Already knows how
  to do subcommands.
- **No abstract base class.** One concrete Engine class. ABC with one
  implementation is ceremony, not architecture.
- **Config as dataclass, not pydantic.** No validation library needed for
  a handful of int/float fields with defaults.
- **mmap for GGUF, direct read for config/tokenizer.** mmap is the right
  tool for large binary files. JSON files are small — just `open().read()`.
- **KV-cache as plain numpy arrays.** No fancy ring buffer or paged
  attention. Fixed-size preallocated arrays. Simple, correct, fast enough.
- **temperature=0 → greedy argmax.** No special code path needed —
  `np.argmax(logits)` is one line.
- **No GPU support.** CPU-only. numpy BLAS is fast enough for demo/CLI.
  GPU is a separate project scope.

---

## Dependencies

```toml
[project]
dependencies = [
    "numpy>=1.24.0",
]
[project.optional-dependencies]
dev = ["pytest>=7.0"]
```

That's it. numpy + pytest. No transformers, no torch, no accelerate.

---

## Do NOT Do

- Do not add PyTorch as a dependency. numpy + BLAS is enough.
- Do not write async/generator API until the sync path works.
- Do not add GPU/CUDA support. CPU-only engine.
- Do not add safetensors loading. GGUF only for v1.
- Do not add streaming text output (token-by-token to stdout) until
  non-streaming generate() is validated.
- Do not add batch inference. Single sequence only.
- Do not add LoRA/adapter loading. YAGNI.
- Do not add a web server or API. CLI only. FastAPI integration is
  a separate integration layer.
- Do not use pydantic, dataclasses is enough for config.
- Do not add type: ignore or mypy overrides. Fix the type, not the checker.
- Do not add logging framework. print() with --verbose flag is fine for CLI.

---

## Verification

After each phase:
1. `python -m pytest tests/ -v` passes
2. CLI generates coherent text on a real GGUF model
3. Memory budget is respected (peak RSS within 10% of target)
4. Output consistency test: streaming output == fullram output
5. No import errors: `python -c "from engine import TransformerModel"`
