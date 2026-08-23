# SovereignAI Python Inference Engine

Local LLM inference with memory-mapped checkpoint loading, configurable
memory budgets, and KV-cache optimization. Minimal dependencies.

## Installation

```bash
cd engine
pip install -e .

# Or just run directly (numpy is the only dependency):
pip install numpy
python -m engine run model.gguf -p "Hello"
```

## Quick Start

```bash
# Generate text
python -m engine run model.gguf -p "The capital of France is"

# Limit output length
python -m engine run model.gguf -p "Explain gravity" -n 64

# JSON stats
python -m engine run model.gguf -p "Hello" --json
```

## Memory Budget

The engine supports configurable memory budgets. When a budget is set,
transformer layer weights are streamed from disk — loaded on demand and
evicted via LRU when the budget is exceeded.

| Budget | Behavior |
|--------|----------|
| `0` (default) | Unlimited — all weights stay in memory |
| `256` | 256MB — tight streaming, most layers evicted |
| `512` | 512MB — moderate streaming |
| `1024` | 1GB — most layers fit, fewer evictions |

```bash
# Tight budget — forces streaming
python -m engine run model.gguf -p "Hello" --budget 256

# Comfortable
python -m engine run model.gguf -p "Hello" --budget 1024

# Unlimited
python -m engine run model.gguf -p "Hello" --budget 0
```

**How to pick a budget:** estimate your model size (params × 2 bytes for
FP16) and add ~10% for KV cache. A 1.1B param model ≈ 2.2GB FP16, so
a 256MB budget means heavy streaming; 2.5GB budget means everything fits.

## Model Info

```bash
python -m engine info model.gguf
```

Output includes: GGUF version, tensor count, architecture config,
tensor type breakdown, estimated size.

## Benchmark

Run generation at multiple budgets to compare performance:

```bash
python -m engine bench model.gguf --budgets 0,256,512,1024
python -m engine bench model.gguf -n 64 --prompt "Explain quantum computing"
```

## Generation Parameters

| Flag | Default | Description |
|------|---------|-------------|
| `-p` | (required) | Text prompt |
| `-n` | 128 | Max tokens to generate |
| `--budget` | 0 | Memory budget in MB (0=unlimited) |
| `-t` | 0.7 | Temperature (0=greedy) |
| `--top-p` | 0.9 | Top-p nucleus sampling |
| `--json` | off | Machine-readable stats |
| `--verbose` | off | Show model info and timing |

## Examples

```bash
# Small budget streaming
./examples/run_small.sh models/tinyllama-1.1B.gguf

# Medium budget
./examples/run_medium.sh models/phi-2.gguf

# Full memory (fastest)
./examples/run_full.sh models/tinyllama-1.1B.gguf
```

## Troubleshooting

**"No vocab.json or tokenizer.json"** — The model directory needs
tokenizer files. For GGUF models, these are usually in the same
directory or inside the GGUF file (extracted by the loader).

**"Not a GGUF file"** — Only GGUF v3 format is supported. Convert
your model with `llama.cpp`'s `convert.py` if needed.

**Slow generation** — Small budgets force frequent weight loading from
disk. Increase `--budget` or use `--budget 0` for maximum speed.

**Index out of bounds** — Tokenizer produced an ID outside the model's
vocabulary range. This usually means a vocab mismatch between the
tokenizer files and the model checkpoint.
