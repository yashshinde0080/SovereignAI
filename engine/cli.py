"""CLI entry point.

Usage:
    python -m engine run model.gguf -p "Hello" [-n N] [--budget MB] [--verbose]
    python -m engine info model.gguf
    python -m engine bench model.gguf [--budgets 256,512,1024]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from .config import ModelConfig
from .gguf import GGUFParser, GGML_TYPE_NAMES
from .tokenizer import Tokenizer
from .loader import CheckpointLoader
from .model import TransformerModel
from .kv_cache import KVCache
from .inference import generate
from .utils import get_peak_rss_mb, Timer


def _load_model(model_path: Path, budget_mb: float = 0):
    """Load config + tokenizer + model from a GGUF file."""
    model_dir = model_path.parent if model_path.is_file() else model_path

    with GGUFParser(model_path) as parser:
        gguf_meta = parser.data.metadata if parser.data else {}
    config = ModelConfig.load(model_dir, gguf_meta)
    tokenizer = Tokenizer(model_dir)
    loader = CheckpointLoader(model_path, budget_mb=budget_mb)
    model = TransformerModel(config, loader)
    return config, tokenizer, loader, model


def cmd_run(args: argparse.Namespace) -> None:
    """Run text generation."""
    model_path = Path(args.model)
    if not model_path.exists():
        print(f"Error: model not found: {model_path}", file=sys.stderr)
        sys.exit(1)

    config, tokenizer, loader, model = _load_model(model_path, args.budget)

    if args.verbose:
        # Time each layer during prefill
        print(f"Model: {config}")
        print(f"Prefilling {len(tokenizer.encode(args.prompt))} tokens...")

    result = generate(
        model=model,
        tokenizer=tokenizer,
        prompt=args.prompt,
        max_tokens=args.n,
        temperature=args.temp,
        top_p=args.top_p,
    )

    print(f"\n> {result.text}\n")

    stats = {
        "tokens": result.n_generated_tokens,
        "time": f"{result.elapsed_s:.3f}s",
        "tok/s": f"{result.tokens_per_second:.1f}",
        "peak_rss": f"{result.peak_rss_mb:.0f}MB",
        "kv_cache": f"{result.kv_cache_mb:.1f}MB",
    }
    if args.budget > 0:
        stats["budget"] = f"{args.budget}MB"

    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        parts = [f"{k}: {v}" for k, v in stats.items()]
        print(f"[{' | '.join(parts)}]")

    loader.close()


def cmd_info(args: argparse.Namespace) -> None:
    """Print model info."""
    model_path = Path(args.model)
    if not model_path.exists():
        print(f"Error: model not found: {model_path}", file=sys.stderr)
        sys.exit(1)

    model_dir = model_path.parent if model_path.is_file() else model_path

    with GGUFParser(model_path) as parser:
        d = parser.data
        print(f"GGUF v{d.version}")
        print(f"Tensors: {d.n_tensors}")
        print(f"Metadata: {len(d.metadata)} keys")

        config = ModelConfig.load(model_dir, d.metadata)
        print(f"\n{config}")

        by_type: dict[int, int] = {}
        for t in d.tensors:
            by_type[t.ggml_type] = by_type.get(t.ggml_type, 0) + 1
        print(f"\nTensor types:")
        for tid, count in sorted(by_type.items()):
            name = GGML_TYPE_NAMES.get(tid, f"unknown({tid})")
            print(f"  {name}: {count} tensors")

        total_bytes = sum(t.nbytes for t in d.tensors)
        if total_bytes > 0:
            print(f"\nEstimated size: {total_bytes / (1024**3):.2f} GB (FP16/FP32)")

        print(f"\nKey metadata:")
        for k in ["general.architecture", "general.name",
                   "llama.context_length", "llama.embedding_length",
                   "llama.block_count", "llama.attention.head_count"]:
            if k in d.metadata:
                print(f"  {k}: {d.metadata[k]}")


def cmd_bench(args: argparse.Namespace) -> None:
    """Benchmark generation at multiple memory budgets."""
    model_path = Path(args.model)
    if not model_path.exists():
        print(f"Error: model not found: {model_path}", file=sys.stderr)
        sys.exit(1)

    budgets = [float(b) for b in args.budgets.split(",")]
    prompt = args.prompt or "The capital of France is"
    max_tokens = args.n

    # Header
    print(f"\nBenchmark: {model_path.name}")
    print(f"Prompt: \"{prompt}\" ({max_tokens} tokens)\n")
    print(f"{'Budget':>10} {'Tokens':>8} {'Time':>8} {'Tok/s':>8} {'Peak RSS':>10} {'KV Cache':>10}")
    print("-" * 60)

    for budget in budgets:
        label = f"{budget:.0f}MB" if budget > 0 else "unlim"
        try:
            config, tokenizer, loader, model = _load_model(model_path, budget)

            with Timer() as t:
                result = generate(
                    model=model, tokenizer=tokenizer,
                    prompt=prompt, max_tokens=max_tokens,
                    temperature=0.0,  # greedy for reproducibility
                )

            rss = get_peak_rss_mb()
            print(
                f"{label:>10} {result.n_generated_tokens:>8} "
                f"{result.elapsed_s:>7.3f}s {result.tokens_per_second:>7.1f} "
                f"{rss:>9.0f}MB {result.kv_cache_mb:>9.1f}MB"
            )

            if args.json_results:
                pass  # collected below

            loader.close()
        except Exception as e:
            print(f"{label:>10} {'ERROR':>8} {str(e)[:30]}")

    if args.json_results:
        print(json.dumps({"budgets": budgets, "prompt": prompt}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sovereign-engine",
        description="SovereignAI Python Inference Engine — local LLM inference",
    )
    sub = parser.add_subparsers(dest="command")

    # ── run ─────────────────────────────────────────────────────────
    p_run = sub.add_parser("run", help="Generate text from a prompt")
    p_run.add_argument("model", help="Path to GGUF model file")
    p_run.add_argument("-p", "--prompt", required=True, help="Text prompt")
    p_run.add_argument("-n", type=int, default=128, help="Max tokens (default: 128)")
    p_run.add_argument("--budget", type=float, default=0,
                       help="Memory budget in MB (0 = unlimited)")
    p_run.add_argument("-t", "--temp", type=float, default=0.7, help="Temperature")
    p_run.add_argument("--top-p", type=float, default=0.9, help="Top-p sampling")
    p_run.add_argument("--json", action="store_true", help="JSON stats output")
    p_run.add_argument("--verbose", "-v", action="store_true", help="Show model info and timing")

    # ── info ────────────────────────────────────────────────────────
    p_info = sub.add_parser("info", help="Print model info")
    p_info.add_argument("model", help="Path to GGUF model file")

    # ── bench ───────────────────────────────────────────────────────
    p_bench = sub.add_parser("bench", help="Benchmark at multiple memory budgets")
    p_bench.add_argument("model", help="Path to GGUF model file")
    p_bench.add_argument("-p", "--prompt", default=None, help="Prompt (default: canned)")
    p_bench.add_argument("-n", type=int, default=32, help="Max tokens per run (default: 32)")
    p_bench.add_argument("--budgets", default="0,256,512",
                         help="Comma-separated budgets in MB (default: 0,256,512)")
    p_bench.add_argument("--json", dest="json_results", action="store_true",
                         help="JSON output")

    args = parser.parse_args()

    if args.command == "run":
        cmd_run(args)
    elif args.command == "info":
        cmd_info(args)
    elif args.command == "bench":
        cmd_bench(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
